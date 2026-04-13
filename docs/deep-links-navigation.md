# Deep Links — Navegacao contextual nas respostas do AI Chat

O MCP pode incluir links de navegacao nas respostas do `/ai/chat`,
permitindo que a aplicacao React direcione o usuario para paginas e
formularios relacionados ao conteudo da resposta.

## Como funciona

```
 Banco de dados               MCP (Claude)              React App
 +-----------------+    +------------------------+    +------------------+
 | AppNavigation   |--->| get_app_routes(entity) |--->| Parse [[nav:..]] |
 | Entity, Route.. |    | Inclui links na reply  |    | <Link to="...">  |
 +-----------------+    +------------------------+    +------------------+
```

1. O Claude detecta que a resposta menciona uma entidade (ex: clientes)
2. Chama a tool `get_app_routes(entity="cliente")` para descobrir rotas
3. Inclui links na resposta no formato `[[nav:/rota|texto]]`
4. O React faz parse e renderiza como links clicaveis do React Router

## 1. Criar a tabela `AppNavigation` no banco de dados

Cada aplicacao que quiser receber deep links deve criar esta tabela
no seu proprio banco de dados (o mesmo apontado pelo `x-connection-name`):

```sql
CREATE TABLE dbo.AppNavigation (
    Id          INT IDENTITY(1,1) PRIMARY KEY,
    Entity      NVARCHAR(100) NOT NULL,
    Action      NVARCHAR(50)  NOT NULL,
    Route       NVARCHAR(500) NOT NULL,
    Label       NVARCHAR(200) NOT NULL,
    Description NVARCHAR(500) NULL
);
```

### Colunas

| Coluna        | Descricao                                                     | Exemplo              |
|---------------|---------------------------------------------------------------|----------------------|
| `Entity`      | Nome da entidade (singular, minusculo)                        | `cliente`            |
| `Action`      | Tipo de acao                                                  | `list`, `detail`, `create`, `edit` |
| `Route`       | Rota do React Router. Use `{id}` para parametros dinamicos    | `/clientes/{id}`     |
| `Label`       | Texto padrao para o link                                      | `Ver cliente`        |
| `Description` | Quando o AI deve sugerir este link (orientacao para o Claude) | `Usar quando mostrar dados de um cliente especifico` |

### Dados de exemplo

```sql
INSERT INTO dbo.AppNavigation (Entity, Action, Route, Label, Description) VALUES
('cliente',  'list',   '/clientes',              'Ver clientes',         'Lista geral de clientes'),
('cliente',  'detail', '/clientes/{id}',          'Ver cliente',          'Detalhes de um cliente especifico'),
('cliente',  'create', '/clientes/novo',          'Cadastrar cliente',    'Formulario de novo cliente'),
('cliente',  'edit',   '/clientes/{id}/editar',   'Editar cliente',       'Formulario de edicao de cliente'),
('pedido',   'list',   '/pedidos',                'Ver pedidos',          'Lista geral de pedidos'),
('pedido',   'detail', '/pedidos/{id}',            'Ver pedido',           'Detalhes de um pedido especifico'),
('pedido',   'create', '/pedidos/novo',            'Novo pedido',          'Formulario de criacao de pedido'),
('produto',  'list',   '/produtos',               'Ver produtos',         'Catalogo de produtos'),
('produto',  'detail', '/produtos/{id}',           'Ver produto',          'Detalhes de um produto'),
('dashboard','list',   '/dashboard',              'Abrir dashboard',      'Painel principal de indicadores');
```

## 2. Formato do link na resposta

O Claude inclui links no texto usando este formato:

```
[[nav:<rota>|<texto do link>]]
```

Exemplos reais que podem aparecer na resposta:

```
Existem 1.243 clientes ativos. [[nav:/clientes?status=ativo|Ver lista de clientes ativos]]

O cliente Maria Silva (ID 42) tem 3 pedidos pendentes.
[[nav:/clientes/42|Ver perfil da Maria]] | [[nav:/pedidos?clienteId=42|Ver pedidos da Maria]]

Para cadastrar um novo produto, use o formulario:
[[nav:/produtos/novo|Cadastrar produto]]
```

## 3. Implementacao no React

### Parser de deep links

```tsx
import { Link } from 'react-router-dom';

// Regex que captura [[nav:<rota>|<texto>]]
const NAV_LINK_REGEX = /\[\[nav:([^\]|]+)\|([^\]]+)\]\]/g;

interface ParsedSegment {
  type: 'text' | 'nav-link';
  content: string;
  route?: string;
}

export function parseDeepLinks(text: string): ParsedSegment[] {
  const segments: ParsedSegment[] = [];
  let lastIndex = 0;

  for (const match of text.matchAll(NAV_LINK_REGEX)) {
    // Texto antes do link
    if (match.index > lastIndex) {
      segments.push({
        type: 'text',
        content: text.slice(lastIndex, match.index),
      });
    }
    // O link em si
    segments.push({
      type: 'nav-link',
      route: match[1],   // /clientes/42
      content: match[2], // Ver perfil da Maria
    });
    lastIndex = match.index + match[0].length;
  }

  // Texto restante apos o ultimo link
  if (lastIndex < text.length) {
    segments.push({ type: 'text', content: text.slice(lastIndex) });
  }

  return segments;
}
```

### Componente de renderizacao

```tsx
interface AiMessageProps {
  text: string;
}

export function AiMessage({ text }: AiMessageProps) {
  const segments = parseDeepLinks(text);

  return (
    <div className="ai-message">
      {segments.map((seg, i) =>
        seg.type === 'nav-link' ? (
          <Link key={i} to={seg.route!} className="ai-nav-link">
            {seg.content}
          </Link>
        ) : (
          <span key={i}>{seg.content}</span>
        )
      )}
    </div>
  );
}
```

### Integracao com Markdown

Se a aplicacao ja renderiza as respostas com um parser Markdown
(ex: `react-markdown`), o parse dos deep links deve acontecer
**antes** do Markdown:

```tsx
import ReactMarkdown from 'react-markdown';

export function AiMessage({ text }: AiMessageProps) {
  // 1. Converter [[nav:...]] em Markdown links internos
  const withLinks = text.replace(
    NAV_LINK_REGEX,
    (_, route, label) => `[${label}](${route})`
  );

  // 2. Renderizar Markdown com handler customizado para links internos
  return (
    <ReactMarkdown
      components={{
        a: ({ href, children }) => {
          // Links internos (comecam com /) usam React Router
          if (href?.startsWith('/')) {
            return <Link to={href}>{children}</Link>;
          }
          // Links externos abrem em nova aba
          return <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>;
        },
      }}
    >
      {withLinks}
    </ReactMarkdown>
  );
}
```

## 4. Comportamento esperado

| Cenario                                  | Resultado                                        |
|------------------------------------------|--------------------------------------------------|
| App TEM tabela `AppNavigation` populada  | Respostas incluem `[[nav:...]]` quando relevante |
| App TEM tabela mas vazia                 | Respostas sem links (lista vazia)                |
| App NAO tem tabela `AppNavigation`       | Respostas sem links (tool retorna `[]`)          |
| Entidade sem rota cadastrada             | Resposta sem link para aquela entidade           |

O mecanismo e **graceful**: aplicacoes que nao criarem a tabela
continuam funcionando normalmente, sem nenhum link nas respostas.

## 5. Query strings e filtros

O Claude pode combinar rotas com query strings para links contextuais.
Se a rota cadastrada e `/clientes` e a conversa e sobre clientes ativos,
o Claude pode gerar:

```
[[nav:/clientes?status=ativo|Ver clientes ativos]]
```

Isso funciona nativamente com o React Router. A aplicacao pode ler
os parametros da URL com `useSearchParams()`.

## 6. Dicas para popular a tabela

- Use nomes de entidade **no singular e em minusculo** (`cliente`, nao `Clientes`)
- A coluna `Description` ajuda o Claude a decidir **quando** sugerir o link
- Cadastre apenas rotas que existem na aplicacao React
- Adicione query params comuns como rotas separadas se quiser links prontos:

```sql
INSERT INTO dbo.AppNavigation VALUES
('cliente', 'list-active',   '/clientes?status=ativo',    'Clientes ativos',    'Quando o contexto for clientes ativos'),
('cliente', 'list-inactive', '/clientes?status=inativo',  'Clientes inativos',  'Quando o contexto for clientes inativos');
```

# Lovable — Integração com os Endpoints de IA (`/ai/health` e `/ai/chat`)

Este documento instrui o Lovable sobre como integrar os endpoints de IA do SupaProxy MCP Server na aplicação front-end.

---

## 1. Configuração — adicionar `mcpUrl` em `src/config/sqlserver.ts`

Abra o arquivo `src/config/sqlserver.ts` e adicione a propriedade `mcpUrl` ao objeto `SQL_SERVER_CONFIG`:

```ts
// src/config/sqlserver.ts

export const SQL_SERVER_CONFIG = {
  // ... demais propriedades já existentes ...
  mcpUrl: "https://si.dev.okeanyachts.com:7065",
};
```

> `mcpUrl` é a URL base do SupaProxy MCP Server. Todos os endpoints de IA devem ser chamados a partir dela.

---

## 2. Endpoints disponíveis

| Método | Caminho                              | Finalidade                              |
|--------|--------------------------------------|-----------------------------------------|
| GET    | `{SQL_SERVER_CONFIG.mcpUrl}/ai/health` | Verificar se o servidor de IA está ativo |
| POST   | `{SQL_SERVER_CONFIG.mcpUrl}/ai/chat`   | Enviar uma mensagem ao agente de IA     |

---

## 3. `GET /ai/health` — Verificação de saúde

Verifica se o endpoint de IA está configurado e operacional. Não requer autenticação.

### Requisição

```
GET {SQL_SERVER_CONFIG.mcpUrl}/ai/health
```

### Resposta de sucesso — `200 OK`

```json
{
  "status": "ok",
  "model": "claude-sonnet-4-6",
  "tools_count": 42,
  "anthropic_configured": true
}
```

| Campo                  | Tipo    | Descrição                                          |
|------------------------|---------|----------------------------------------------------|
| `status`               | string  | `"ok"` quando o servidor está saudável             |
| `model`                | string  | Identificador do modelo LLM em uso                 |
| `tools_count`          | number  | Quantidade de ferramentas MCP registradas           |
| `anthropic_configured` | boolean | `true` se a chave da API Anthropic está configurada |

### Exemplo de uso (TypeScript)

```ts
const res = await fetch(`${SQL_SERVER_CONFIG.mcpUrl}/ai/health`);
const health = await res.json();

if (health.status !== "ok" || !health.anthropic_configured) {
  console.warn("Servidor de IA indisponível.");
}
```

---

## 4. `POST /ai/chat` — Chat com o agente de IA

Envia uma mensagem ao agente de IA e recebe a resposta após o loop agêntico completo (o agente pode consultar o banco de dados, executar ferramentas e raciocinar antes de responder).

### Headers obrigatórios

Todos os três headers abaixo **devem** ser enviados em cada requisição:

| Header               | Valor                                    |
|----------------------|------------------------------------------|
| `x-api-key`          | `{SQL_SERVER_CONFIG.apiKey}`             |
| `x-connection-name`  | `{SQL_SERVER_CONFIG.connectionName}`     |
| `Authorization`      | `Bearer {TOKEN DO USUÁRIO LOGADO}`       |

> O token do usuário logado (`Authorization: Bearer ...`) deve ser o JWT da sessão ativa, obtido do provedor de autenticação da aplicação (ex: Supabase `session.access_token`).

### Requisição

```
POST {SQL_SERVER_CONFIG.mcpUrl}/ai/chat
Content-Type: application/json
Authorization: Bearer <jwt_do_usuario>
x-api-key: <SQL_SERVER_CONFIG.apiKey>
x-connection-name: <SQL_SERVER_CONFIG.connectionName>
```

**Body:**

```json
{
  "message": "Quantos clientes ativos existem?",
  "conversation_history": [
    { "role": "user",      "content": "Olá!" },
    { "role": "assistant", "content": "Olá! Como posso ajudar?" }
  ]
}
```

| Campo                  | Tipo                         | Obrigatório | Descrição                                                                 |
|------------------------|------------------------------|-------------|---------------------------------------------------------------------------|
| `message`              | string                       | Sim         | Mensagem atual do usuário                                                 |
| `conversation_history` | `{ role, content }[]`        | Não         | Histórico anterior da conversa (roles aceitos: `"user"` e `"assistant"`) |

### Resposta de sucesso — `200 OK`

```json
{
  "reply": "Existem 1.243 clientes ativos no momento.",
  "model": "claude-sonnet-4-6",
  "stop_reason": "end_turn"
}
```

| Campo         | Tipo   | Descrição                                                              |
|---------------|--------|------------------------------------------------------------------------|
| `reply`       | string | Resposta final do agente de IA                                         |
| `model`       | string | Modelo LLM que gerou a resposta                                        |
| `stop_reason` | string | Motivo de parada: `"end_turn"` (concluiu) ou outro valor da Anthropic |

### Respostas de erro

| Código | Situação                                                  |
|--------|-----------------------------------------------------------|
| `400`  | Body JSON inválido                                        |
| `401`  | Header `Authorization`, `x-api-key` ou `x-connection-name` ausente ou inválido |
| `500`  | Erro interno no servidor                                  |
| `502`  | Falha na comunicação com a API da Anthropic               |

### Exemplo de uso (TypeScript)

```ts
import { SQL_SERVER_CONFIG } from "@/config/sqlserver";

interface ConversationMessage {
  role: "user" | "assistant";
  content: string;
}

interface ChatResponse {
  reply: string;
  model: string;
  stop_reason: string;
}

async function sendChatMessage(
  message: string,
  conversationHistory: ConversationMessage[],
  userToken: string
): Promise<ChatResponse> {
  const response = await fetch(`${SQL_SERVER_CONFIG.mcpUrl}/ai/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${userToken}`,
      "x-api-key": SQL_SERVER_CONFIG.apiKey,
      "x-connection-name": SQL_SERVER_CONFIG.connectionName,
    },
    body: JSON.stringify({
      message,
      conversation_history: conversationHistory,
    }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail ?? `HTTP ${response.status}`);
  }

  return response.json() as Promise<ChatResponse>;
}
```

---

## 5. Fluxo completo recomendado

```
Usuário digita mensagem
        ↓
Obter token JWT da sessão ativa (ex: supabase.auth.getSession())
        ↓
POST {SQL_SERVER_CONFIG.mcpUrl}/ai/chat
  Headers: Authorization, x-api-key, x-connection-name
  Body: { message, conversation_history }
        ↓
Aguardar resposta (o agente pode levar alguns segundos — exiba um indicador de carregamento)
        ↓
Exibir { reply } na interface
        ↓
Adicionar { role: "user", content: message } e { role: "assistant", content: reply }
ao histórico local para a próxima chamada
```

---

## 6. Notas importantes

- **Manter o histórico no cliente:** O servidor é stateless. O campo `conversation_history` deve ser gerenciado localmente e enviado a cada chamada para preservar o contexto da conversa.
- **Indicador de carregamento:** O agente pode executar múltiplas ferramentas antes de responder. Exiba um estado de carregamento enquanto aguarda.
- **Token expirado:** Se a resposta for `401`, a sessão do usuário expirou. Redirecione para o login.
- **CORS:** O servidor já está configurado com `allow_origins: ["*"]`, portanto não há restrições de origem.

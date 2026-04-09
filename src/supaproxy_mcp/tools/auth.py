"""Authentication and user management tools for SupaProxy."""

import base64
import json
import logging
from typing import Optional

import httpx

from ..header_context import forwarded_token

logger = logging.getLogger(__name__)


def _extract_user_id_from_token(token: Optional[str]) -> Optional[str]:
    """Decode the JWT payload (without verification) and return the user ID.

    The SupaProxy issues JWTs whose ``sub`` claim contains the user ID as
    a GUID string.  We only need to read it — the backend will verify the
    signature when we forward the token in the Authorization header.
    """
    if not token:
        return None
    try:
        payload_b64 = token.split(".")[1]
        # Fix padding — base64 requires length to be a multiple of 4
        payload_b64 += "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        return payload.get("sub")
    except Exception:
        logger.warning("Failed to extract user_id from JWT payload", exc_info=True)
        return None


def register(mcp, client):  # noqa: ANN001
    """Register auth and user management tools on the given FastMCP instance."""

    # ------------------------------------------------------------------
    # Current user
    # ------------------------------------------------------------------

    @mcp.tool()
    async def get_current_user() -> str:
        """Retrieve the profile of the currently authenticated user.

        IMPORTANT: Always call this tool first whenever the user refers to
        themselves ("quem sou eu", "meu perfil", "meus dados", etc.).
        The identity is derived automatically from the JWT token present
        in the request — no login or extra parameters are needed.

        Returns:
            JSON object with the current user's profile (id, email,
            user_metadata, app_metadata with roles), or an error message.
        """
        try:
            token = forwarded_token.get()
            logger.info(
                "get_current_user called — forwarded_token present: %s",
                token is not None,
            )
            user_id = _extract_user_id_from_token(token)
            if user_id is None:
                return (
                    "AUTHENTICATION ERROR: Could not determine the current user. "
                    "The session token is missing or does not contain a valid user "
                    "identifier.  Do NOT ask the user for their email or password. "
                    "Inform them that their session may have expired and they should "
                    "reload the application."
                )
            result = await client.get("/auth/user", include_connection=False)
            return json.dumps(result, indent=2, ensure_ascii=False)
        except httpx.HTTPStatusError as exc:
            logger.error(
                "get_current_user failed — status=%s body=%s",
                exc.response.status_code,
                exc.response.text,
            )
            if exc.response.status_code == 401:
                return (
                    "AUTHENTICATION ERROR: The user's session token is expired "
                    "or invalid.  Do NOT ask the user for their email or password — "
                    "they cannot log in through this interface.  Instead, inform "
                    "them that their session has expired and they should reload "
                    "the application to obtain a new token."
                )
            return f"Error {exc.response.status_code}: {exc.response.text}"
        except Exception as exc:
            logger.exception("Unexpected error in get_current_user")
            return f"Unexpected error: {exc}"

    @mcp.tool()
    async def update_current_user(
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        password: Optional[str] = None,
        department: Optional[str] = None,
        image_id: Optional[str] = None,
    ) -> str:
        """Update the profile of the currently authenticated user.

        Only the fields you provide will be updated; omitted fields keep
        their current values.

        Args:
            first_name: New first name.
            last_name: New last name.
            password: New password (min 8 characters).
            department: New department.
            image_id: New profile image ID (GUID from storage).

        Returns:
            JSON object of the updated user profile, or an error message.
        """
        try:
            body: dict = {}
            data_section: dict = {}
            if first_name is not None:
                data_section["first_name"] = first_name
            if last_name is not None:
                data_section["last_name"] = last_name
            if department is not None:
                data_section["department"] = department
            if data_section:
                body["data"] = data_section
            if password is not None:
                body["password"] = password
            if image_id is not None:
                body["imageId"] = image_id
            result = await client.put("/auth/user", json=body, include_connection=False)
            return json.dumps(result, indent=2, ensure_ascii=False)
        except httpx.HTTPStatusError as exc:
            return f"Error {exc.response.status_code}: {exc.response.text}"
        except Exception as exc:
            logger.exception("Unexpected error in update_current_user")
            return f"Unexpected error: {exc}"

    # ------------------------------------------------------------------
    # Admin user management
    # ------------------------------------------------------------------

    @mcp.tool()
    async def admin_list_users() -> str:
        """List all users registered in the system.

        Requires administrator privileges.

        Returns:
            JSON array of user objects, or an error message.
        """
        try:
            result = await client.get("/auth/admin/users", include_connection=False)
            return json.dumps(result, indent=2, ensure_ascii=False)
        except httpx.HTTPStatusError as exc:
            return f"Error {exc.response.status_code}: {exc.response.text}"
        except Exception as exc:
            logger.exception("Unexpected error in admin_list_users")
            return f"Unexpected error: {exc}"

    @mcp.tool()
    async def admin_create_user(
        email: str,
        password: str,
        first_name: str,
        last_name: str,
        roles: Optional[list[str]] = None,
        is_active: Optional[bool] = None,
        department: Optional[str] = None,
    ) -> str:
        """Create a new user account (admin only).

        Args:
            email: The user's unique email address.
            password: Initial password (min 8 chars, must contain letters and numbers).
            first_name: User's first name.
            last_name: User's last name.
            roles: Optional list of role names to assign (e.g. ["admin", "user"]).
            is_active: Whether the account is active (default True).
            department: Optional department name.

        Returns:
            JSON object of the newly created user, or an error message.
        """
        try:
            body: dict = {
                "email": email,
                "password": password,
                "first_name": first_name,
                "last_name": last_name,
            }
            if roles is not None:
                body["roles"] = roles
            if is_active is not None:
                body["is_active"] = is_active
            if department is not None:
                body["department"] = department
            result = await client.post("/auth/admin/users", json=body, include_connection=False)
            return json.dumps(result, indent=2, ensure_ascii=False)
        except httpx.HTTPStatusError as exc:
            return f"Error {exc.response.status_code}: {exc.response.text}"
        except Exception as exc:
            logger.exception("Unexpected error in admin_create_user")
            return f"Unexpected error: {exc}"

    @mcp.tool()
    async def admin_update_user(
        user_id: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        roles: Optional[list[str]] = None,
        is_active: Optional[bool] = None,
        new_password: Optional[str] = None,
        department: Optional[str] = None,
    ) -> str:
        """Update an existing user's profile (admin only).

        Only the fields you provide will be updated.

        Args:
            user_id: The GUID of the user to update.
            first_name: New first name.
            last_name: New last name.
            roles: New list of role names (replaces all existing roles).
            is_active: Activate or deactivate the account.
            new_password: New password (min 8 chars).
            department: New department.

        Returns:
            JSON object of the updated user, or an error message.
        """
        try:
            body: dict = {}
            if first_name is not None:
                body["first_name"] = first_name
            if last_name is not None:
                body["last_name"] = last_name
            if roles is not None:
                body["roles"] = roles
            if is_active is not None:
                body["is_active"] = is_active
            if new_password is not None:
                body["new_password"] = new_password
            if department is not None:
                body["department"] = department
            result = await client.put(
                f"/auth/admin/users/{user_id}", json=body, include_connection=False,
            )
            return json.dumps(result, indent=2, ensure_ascii=False)
        except httpx.HTTPStatusError as exc:
            return f"Error {exc.response.status_code}: {exc.response.text}"
        except Exception as exc:
            logger.exception("Unexpected error in admin_update_user")
            return f"Unexpected error: {exc}"

    @mcp.tool()
    async def admin_delete_user(user_id: str, hard: bool = False) -> str:
        """Delete a user account (admin only).

        Args:
            user_id: The GUID of the user to delete.
            hard: If True, permanently removes the user.  If False (default),
                  performs a soft delete (deactivation).

        Returns:
            JSON confirmation, or an error message.
        """
        try:
            result = await client.delete(
                f"/auth/admin/users/{user_id}?hard={'true' if hard else 'false'}",
                include_connection=False,
            )
            return json.dumps(result, indent=2, ensure_ascii=False)
        except httpx.HTTPStatusError as exc:
            return f"Error {exc.response.status_code}: {exc.response.text}"
        except Exception as exc:
            logger.exception("Unexpected error in admin_delete_user")
            return f"Unexpected error: {exc}"

    # ------------------------------------------------------------------
    # Role management (admin)
    # ------------------------------------------------------------------

    @mcp.tool()
    async def list_roles() -> str:
        """List all roles available in the system (admin only).

        Returns:
            JSON array of role objects (id, name, description).
        """
        try:
            result = await client.get("/auth/admin/roles", include_connection=False)
            return json.dumps(result, indent=2, ensure_ascii=False)
        except httpx.HTTPStatusError as exc:
            return f"Error {exc.response.status_code}: {exc.response.text}"
        except Exception as exc:
            logger.exception("Unexpected error in list_roles")
            return f"Unexpected error: {exc}"

    @mcp.tool()
    async def create_role(name: str, description: Optional[str] = None) -> str:
        """Create a new role (admin only).

        Args:
            name: Unique role name (e.g. "editor", "viewer").
            description: Optional description of the role's purpose.

        Returns:
            JSON object of the created role, or an error message.
        """
        try:
            body: dict = {"name": name}
            if description is not None:
                body["description"] = description
            result = await client.post("/auth/admin/roles", json=body, include_connection=False)
            return json.dumps(result, indent=2, ensure_ascii=False)
        except httpx.HTTPStatusError as exc:
            return f"Error {exc.response.status_code}: {exc.response.text}"
        except Exception as exc:
            logger.exception("Unexpected error in create_role")
            return f"Unexpected error: {exc}"

    @mcp.tool()
    async def update_role(
        role_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> str:
        """Update an existing role (admin only).

        Args:
            role_id: The GUID of the role to update.
            name: New role name.
            description: New description.

        Returns:
            JSON object of the updated role, or an error message.
        """
        try:
            body: dict = {}
            if name is not None:
                body["name"] = name
            if description is not None:
                body["description"] = description
            result = await client.put(
                f"/auth/admin/roles/{role_id}", json=body, include_connection=False,
            )
            return json.dumps(result, indent=2, ensure_ascii=False)
        except httpx.HTTPStatusError as exc:
            return f"Error {exc.response.status_code}: {exc.response.text}"
        except Exception as exc:
            logger.exception("Unexpected error in update_role")
            return f"Unexpected error: {exc}"

    @mcp.tool()
    async def delete_role(role_id: str) -> str:
        """Delete a role (admin only).

        Args:
            role_id: The GUID of the role to delete.

        Returns:
            JSON confirmation, or an error message.
        """
        try:
            result = await client.delete(
                f"/auth/admin/roles/{role_id}", include_connection=False,
            )
            return json.dumps(result, indent=2, ensure_ascii=False)
        except httpx.HTTPStatusError as exc:
            return f"Error {exc.response.status_code}: {exc.response.text}"
        except Exception as exc:
            logger.exception("Unexpected error in delete_role")
            return f"Unexpected error: {exc}"

    @mcp.tool()
    async def set_user_roles(user_id: str, roles: list[str]) -> str:
        """Replace all roles for a user (admin only).

        Args:
            user_id: The GUID of the user.
            roles: List of role names to assign.  Replaces all existing roles.
                   Example: ["admin", "editor"]

        Returns:
            JSON confirmation, or an error message.
        """
        try:
            result = await client.put(
                f"/auth/admin/users/{user_id}/roles",
                json={"roles": roles},
                include_connection=False,
            )
            return json.dumps(result, indent=2, ensure_ascii=False)
        except httpx.HTTPStatusError as exc:
            return f"Error {exc.response.status_code}: {exc.response.text}"
        except Exception as exc:
            logger.exception("Unexpected error in set_user_roles")
            return f"Unexpected error: {exc}"

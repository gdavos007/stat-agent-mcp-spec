"""Narrow ASGI bearer authentication for the controlled HTTP demo."""

from __future__ import annotations

import secrets

from pydantic import SecretStr
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

_UNAUTHORIZED_RESPONSE = {"error": "unauthorized"}
_AUTHENTICATE_HEADER = {"WWW-Authenticate": "Bearer"}


class BearerAuthMiddleware:
    """Require one shared bearer token for an MCP path and its subpaths."""

    def __init__(
        self,
        app: ASGIApp,
        bearer_token: SecretStr,
        *,
        protected_path: str = "/mcp",
    ) -> None:
        self._app = app
        self._expected_token = bearer_token.get_secret_value().encode("ascii")
        self._protected_path = protected_path.rstrip("/") or "/"

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not self._is_protected(str(scope.get("path", ""))):
            await self._app(scope, receive, send)
            return

        authorization_values = [
            value for name, value in scope.get("headers", []) if name.lower() == b"authorization"
        ]
        if len(authorization_values) != 1 or not self._is_authorized(authorization_values[0]):
            response = JSONResponse(
                _UNAUTHORIZED_RESPONSE,
                status_code=401,
                headers=_AUTHENTICATE_HEADER,
            )
            await response(scope, receive, send)
            return

        await self._app(scope, receive, send)

    def _is_protected(self, path: str) -> bool:
        return path == self._protected_path or path.startswith(f"{self._protected_path}/")

    def _is_authorized(self, authorization: bytes) -> bool:
        scheme, separator, supplied_token = authorization.partition(b" ")
        if (
            separator != b" "
            or scheme.lower() != b"bearer"
            or not supplied_token
            or any(character in b" \t\r\n" for character in supplied_token)
        ):
            return False
        return secrets.compare_digest(supplied_token, self._expected_token)

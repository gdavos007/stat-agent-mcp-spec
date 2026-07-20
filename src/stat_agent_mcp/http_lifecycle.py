"""ASGI lifespan behavior for concise HTTP readiness logging."""

from __future__ import annotations

import logging

from starlette.types import ASGIApp, Message, Receive, Scope, Send


class ReadinessLoggingMiddleware:
    """Log readiness only after the wrapped application finishes startup."""

    def __init__(self, app: ASGIApp, logger: logging.Logger) -> None:
        self._app = app
        self._logger = logger

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "lifespan":
            await self._app(scope, receive, send)
            return

        async def send_with_readiness(message: Message) -> None:
            if message["type"] == "lifespan.startup.complete":
                self._logger.info("HTTP server ready")
            await send(message)

        await self._app(scope, receive, send_with_readiness)

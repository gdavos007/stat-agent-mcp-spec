"""Minimal public HTTP health route registration."""

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse


def register_health_route(server: FastMCP) -> None:
    """Register a cheap, non-secret-bearing readiness response."""

    async def health(_request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok"})

    route_decorator = server.custom_route(
        "/health",
        methods=["GET"],
        include_in_schema=False,
    )
    route_decorator(health)

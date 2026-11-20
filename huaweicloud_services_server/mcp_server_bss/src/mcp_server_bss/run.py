"""Entry point para mcp-server-bss: server standalone con las 3 tools de billing.

Reutiliza el patrón de transporte de assets/utils/server.py (mcp.server.Server +
StreamableHTTP/SSE/stdio) y el middleware multi-tenant (per_request_creds).
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import uuid
from pathlib import Path
from typing import AsyncIterator

import uvicorn
from mcp.server import Server
from mcp.server.fastmcp.utilities.logging import configure_logging, get_logger
from mcp.server.sse import SseServerTransport
from mcp.server.stdio import stdio_server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.types import Tool, TextContent
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route
from starlette.types import Receive, Scope, Send

from assets.utils.bss_tools import BSS_TOOLS, call_bss_tool
from assets.utils.per_request_creds import set_request_headers, reset_request_headers

logger = get_logger(__name__)
configure_logging("INFO")


def _build_server() -> Server:
    server = Server("hwc-mcp-server-bss")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return BSS_TOOLS

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        try:
            result = call_bss_tool(name, arguments)
            return [TextContent(type="text", text=result)]
        except Exception as ex:
            logger.error(f"BSS tool {name} failed: {ex}", exc_info=True)
            raise

    return server


async def run_stdio(server: Server) -> None:
    async with stdio_server() as streams:
        await server.run(streams[0], streams[1], server.create_initialization_options())


async def run_http(server: Server, port: int) -> None:
    session_manager = StreamableHTTPSessionManager(app=server, event_store=None, stateless=True)

    async def handle_streamable_http(scope: Scope, receive: Receive, send: Send) -> None:
        token = None
        if scope.get("type") == "http":
            raw = scope.get("headers") or []
            headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in raw}
            token = set_request_headers(headers)
        try:
            await session_manager.handle_request(scope, receive, send)
        finally:
            if token is not None:
                reset_request_headers(token)

    @contextlib.asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        async with session_manager.run():
            yield

    app = Starlette(debug=True, routes=[Mount("/mcp", app=handle_streamable_http)], lifespan=lifespan)
    cfg = uvicorn.Config(app, host="0.0.0.0", port=port)
    await uvicorn.Server(cfg).serve()


async def run_sse(server: Server, port: int) -> None:
    sse = SseServerTransport("/messages/")

    async def handle_sse_connection(request):
        headers = {str(k).lower(): str(v) for k, v in request.headers.items()}
        token = set_request_headers(headers)
        try:
            async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
                await server.run(streams[0], streams[1], server.create_initialization_options())
        finally:
            reset_request_headers(token)
        return JSONResponse({"status": "ok"}, status_code=200)

    app = Starlette(routes=[Route("/sse", endpoint=handle_sse_connection), Mount("/messages/", app=sse.handle_post_message)], debug=True)
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_headers=["*"], allow_credentials=True, allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
    cfg = uvicorn.Config(app, host="0.0.0.0", port=port)
    await uvicorn.Server(cfg).serve()


def main() -> None:
    parser = argparse.ArgumentParser(description="Huawei Cloud BSS (billing) MCP server")
    parser.add_argument("-t", "--transport", choices=["stdio", "http", "sse"], default="http")
    parser.add_argument("-p", "--port", type=int, default=8888)
    args = parser.parse_args()

    server = _build_server()
    if args.transport == "stdio":
        asyncio.run(run_stdio(server))
    elif args.transport == "sse":
        asyncio.run(run_sse(server, args.port))
    else:
        asyncio.run(run_http(server, args.port))


if __name__ == "__main__":
    main()

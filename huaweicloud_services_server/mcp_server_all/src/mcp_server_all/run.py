"""Entry point para mcp-server-all: server unificado que carga TODOS los
servicios de Huawei Cloud (~174) + BSS billing en un solo endpoint MCP.

Esto es necesario para el multi-tenant por headers HTTP: un solo endpoint
permite que las credenciales por request (X-Huawei-Access-Key etc.) operen
sobre todos los servicios en una sola sesión.

Las tools se namespacen como ``<service_code>__<tool_name>`` para evitar
colisiones entre servicios. Las tools BSS mantienen su nombre sin prefijo
(bss_list_resource_records, bss_total_cost, bss_cycle_breakdown).

Entry points individuales (mcp-server-ecs, etc.) siguen disponibles para uso
sin multi-tenant o cuando solo se necesita un servicio.
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
from huaweicloudsdkcore.exceptions.exceptions import ClientRequestException
from mcp.server import Server
from mcp.server.fastmcp.exceptions import ToolError
from mcp.server.fastmcp.utilities.logging import configure_logging, get_logger
from mcp.server.sse import SseServerTransport
from mcp.server.stdio import stdio_server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.types import Tool, TextContent, ImageContent, EmbeddedResource
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route
from starlette.types import Receive, Scope, Send

from assets.utils.hwc_tools import (
    create_api_client,
    build_http_info,
    load_openapi,
    filter_parameters,
    load_config,
)
from assets.utils.openapi import OpenAPIToToolsConverter
from assets.utils.bss_tools import BSS_TOOLS, call_bss_tool
from assets.utils.per_request_creds import (
    set_request_headers,
    reset_request_headers,
    request_region,
    resolve_credentials,
)

logger = get_logger(__name__)
configure_logging("INFO")

# Raíz del catálogo de servicios.
_SERVICES_ROOT = Path(__file__).resolve().parents[4]  # huaweicloud_services_server/
_NS_SEP = "__"


def _discover_services() -> dict[str, dict]:
    """Descubre todos los config.yaml bajo huaweicloud_services_server/mcp_server_*/src/*/config/.

    Devuelve {service_code: {openapi_dict, tools, x_host, config}}.
    """
    services: dict[str, dict] = {}
    config_files = sorted(_SERVICES_ROOT.glob("mcp_server_*/src/*/config/config.yaml"))
    logger.info(f"Descubiertos {len(config_files)} config.yaml de servicios")
    for cfg_path in config_files:
        try:
            config = load_config(cfg_path)
            if not config:
                continue
            code = config.service_code.lower()
            openapi_path = cfg_path.parent / f"{code}.json"
            if not openapi_path.exists():
                continue
            openapi_dict = load_openapi(openapi_path)
            if not openapi_dict:
                continue
            tools = OpenAPIToToolsConverter(openapi_dict).convert()
            x_host = openapi_dict["info"]["x-host"]
            services[code] = {
                "openapi_dict": openapi_dict,
                "tools": tools,
                "x_host": x_host,
                "config": config,
            }
            logger.info(f"  cargado {code}: {len(tools)} tools")
        except Exception as e:
            logger.warning(f"  saltando {cfg_path}: {e}")
    return services


def _build_all_tools(services: dict[str, dict]) -> list[Tool]:
    """Aplana todas las tools con namespace <service_code>__<tool_name> + BSS."""
    all_tools: list[Tool] = []
    for code, svc in services.items():
        for t in svc["tools"]:
            ns_name = f"{code}{_NS_SEP}{t.name}"
            all_tools.append(Tool(
                name=ns_name,
                description=f"[{code.upper()}] {t.description}",
                inputSchema=t.inputSchema,
            ))
    # BSS tools sin namespace (ya tienen prefijo bss_).
    all_tools.extend(BSS_TOOLS)
    return all_tools


def _build_server(services: dict[str, dict], all_tools: list[Tool]) -> Server:
    server = Server("hwc-mcp-server-all")
    # Mapeo tool_name namespacedeada -> (service_code, original_name).
    dispatch_map: dict[str, tuple[str, str]] = {}
    for code, svc in services.items():
        for t in svc["tools"]:
            dispatch_map[f"{code}{_NS_SEP}{t.name}"] = (code, t.name)
    bss_names = {t.name for t in BSS_TOOLS}

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return all_tools

    @server.call_tool()
    async def call_tool(
        name: str, arguments: dict
    ) -> list[TextContent | ImageContent | EmbeddedResource]:
        # --- BSS tools ---
        if name in bss_names:
            try:
                result = call_bss_tool(name, arguments)
                return [TextContent(type="text", text=result)]
            except Exception as ex:
                logger.error(f"BSS tool {name} failed: {ex}", exc_info=True)
                raise

        # --- Service tools ---
        if name not in dispatch_map:
            raise ToolError({"code": "UNKNOWN_TOOL", "message": f"Tool {name} not found"})

        code, orig_name = dispatch_map[name]
        svc = services[code]
        openapi_dict = svc["openapi_dict"]
        svc_tools = svc["tools"]
        x_host = svc["x_host"]

        region = arguments.get("region") or "cn-north-4"
        header_region = request_region()
        if header_region and not arguments.get("region"):
            region = header_region

        ak, sk = resolve_credentials(svc["config"].ak, svc["config"].sk)
        if not ak or not sk:
            raise ToolError({
                "code": "MISSING_CREDENTIALS",
                "message": "HUAWEI_ACCESS_KEY or HUAWEI_SECRET_KEY not configured",
            })

        client = create_api_client(ak, sk, x_host, region)
        try:
            arguments = filter_parameters(arguments)
            http_info = build_http_info(orig_name, arguments, openapi_dict, svc_tools)
            response = client.do_http_request(**http_info)
            response_data = response.json() if response and response.content else {}
            return [TextContent(
                type="text",
                text=json.dumps(response_data, indent=2, ensure_ascii=False),
            )]
        except ClientRequestException as ex:
            logger.error(f"API request failed ({code}/{orig_name}): {ex.error_msg}")
            raise ValueError(ex.error_msg)
        except Exception as ex:
            logger.error(f"Unexpected error ({code}/{orig_name}): {ex}")
            raise

    return server


# --- Transporte (con middleware multi-tenant) ---

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
    parser = argparse.ArgumentParser(description="Huawei Cloud MCP server (all services + BSS, unified)")
    parser.add_argument("-t", "--transport", choices=["stdio", "http", "sse"], default="http")
    parser.add_argument("-p", "--port", type=int, default=8888)
    args = parser.parse_args()

    logger.info("Cargando todos los servicios de Huawei Cloud...")
    services = _discover_services()
    logger.info(f"Total: {len(services)} servicios cargados")
    all_tools = _build_all_tools(services)
    logger.info(f"Total: {len(all_tools)} tools (incluye BSS)")

    server = _build_server(services, all_tools)
    if args.transport == "stdio":
        asyncio.run(run_stdio(server))
    elif args.transport == "sse":
        asyncio.run(run_sse(server, args.port))
    else:
        asyncio.run(run_http(server, args.port))


if __name__ == "__main__":
    main()

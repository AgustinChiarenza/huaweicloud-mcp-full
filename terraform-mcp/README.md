# terraform-mcp

MCP server (Go) para lookups contra el Terraform Registry: módulos, providers,
versiones y docs públicas. Se consume vía **streamable HTTP en `/mcp`**.

## Build

El `Dockerfile` incluido es el del upstream oficial
[`hashicorp/terraform-mcp-server`](https://github.com/hashicorp/terraform-mcp-server)
(MPL-2.0). Es multi-stage: compila el binario con `golang:1.26-alpine` y lo
empaqueta en `scratch`.

```bash
docker build --target dev -t terraform-mcp-server:dev ./terraform-mcp
```

O directamente con el compose del repo raíz:

```bash
docker compose up -d --build   # buildea hwc-mcp-all + terraform-mcp
```

Arranque manual:

```bash
docker run -d -p 8088:8080 terraform-mcp-server:dev \
  streamable-http --transport-host 0.0.0.0 --transport-port 8080
```

- El `--transport-host 0.0.0.0` es necesario para que otros containers lo
  reachen por service name (el default `127.0.0.1` no se reacha entre containers).
- Loguea un warning "No Terraform token" → las tools de registry **privado (TFE)**
  quedan off, pero el lookup **público** de módulos/providers funciona igual.

## Tools expuestas (10)

- `search_modules(module_query)` — busca módulos en el registry público.
- `get_latest_module_version(module_id)` — última versión de un módulo.
- `get_module_details(module_id)` — detalles de un módulo.
- `get_latest_provider_version(namespace, name)` — última versión de un provider.
- `get_provider_details(namespace, name)` — detalles de un provider.
- `get_provider_capabilities(namespace, name)` — capabilities de un provider.
- `search_provider_docs(...)` — busca docs de providers.
- `get_policy_details(...)` — detalles de políticas (Sentinel/OPA).
- `search_policies(...)` — busca políticas.
- `generate_search_query_configuration(...)` — helper de query config.

(+ tools de registry privado TFE si hay `TFE_TOKEN`.)

# mcp-server-hwc-ops

A custom Huawei Cloud operations MCP server that provides read-only tools for common cloud operations across multiple services (ECS, VPC, OBS, CBR, CES, CTS, LTS, IAM).

## Purpose

This MCP server acts as a practical operations companion for AI agents managing Huawei Cloud infrastructure. It consolidates the most common read-only queries from multiple services into a single server, eliminating the need to run separate MCP servers for each service.

## Installation

```bash
# Clone and install
git clone https://github.com/HuaweiCloudDeveloper/mcp-server.git
cd mcp-server
pip install -e .

# Or with uv
uv pip install -e .
```

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `HUAWEI_ACCESS_KEY` | Yes | Huawei Cloud Access Key (AK) |
| `HUAWEI_SECRET_KEY` | Yes | Huawei Cloud Secret Key (SK) |
| `HUAWEICLOUD_SDK_AK` | Alternative | Alternative name for AK |
| `HUAWEICLOUD_SDK_SK` | Alternative | Alternative name for SK |
| `HUAWEI_PROJECT_ID` | No | Project ID (auto-derived if not set) |
| `MCP_SERVER_MODE` | No | Transport mode: `stdio`, `http`, `sse` |
| `MCP_SERVER_PORT` | No | Port for http/sse mode |
| `ALLOW_HWC_WRITE_TOOLS` | No | Feature flag for write tools (default: `false`) |

## Commands

```bash
# stdio mode (default, for CLI/IDE integration)
mcp-server-hwc-ops -t stdio
uv run mcp-server-hwc-ops -t stdio

# HTTP mode (StreamableHTTP)
mcp-server-hwc-ops -t http -p 8888
uv run mcp-server-hwc-ops -t http -p 8888

# SSE mode
mcp-server-hwc-ops -t sse -p 8888
uv run mcp-server-hwc-ops -t sse -p 8888
```

## Available Tools

| Tool | Service | Description |
|---|---|---|
| `ecs_list_servers` | ECS | List ECS instances (id, name, status, flavor, vpc_id, addresses, created, az) |
| `ecs_show_server` | ECS | Show details of one ECS instance |
| `vpc_list_vpcs` | VPC | List VPCs in a region |
| `vpc_list_subnets` | VPC | List subnets, optionally filtered by VPC |
| `obs_list_buckets` | OBS | List OBS buckets (name, location, creation date) |
| `cbr_list_vaults` | CBR | List backup vaults |
| `cbr_list_backups` | CBR | List backups, optionally filtered by vault |
| `ces_list_alarms` | CES | List Cloud Eye alarms |
| `cts_list_traces` | CTS | List recent audit traces/events |
| `lts_list_log_groups` | LTS | List log groups |
| `iam_get_current_user_or_projects` | IAM | List projects for the configured credentials |

## OpenCode Config Examples

### stdio mode

```json
{
  "mcpServers": {
    "hwc-ops": {
      "command": "uv",
      "args": ["run", "mcp-server-hwc-ops", "-t", "stdio"],
      "env": {
        "HUAWEI_ACCESS_KEY": "YOUR_AK",
        "HUAWEI_SECRET_KEY": "YOUR_SK"
      }
    }
  }
}
```

### HTTP mode

```json
{
  "mcpServers": {
    "hwc-ops": {
      "url": "http://localhost:8888/mcp",
      "env": {
        "HUAWEI_ACCESS_KEY": "YOUR_AK",
        "HUAWEI_SECRET_KEY": "YOUR_SK"
      }
    }
  }
}
```

### Claude Desktop config

```json
{
  "mcpServers": {
    "hwc-ops": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/mcp-server", "mcp-server-hwc-ops", "-t", "stdio"],
      "env": {
        "HUAWEI_ACCESS_KEY": "YOUR_AK",
        "HUAWEI_SECRET_KEY": "YOUR_SK"
      }
    }
  }
}
```

## Example Prompts

```
- "List all ECS instances in la-south-2"
- "Show me details for ECS server abc-123"
- "What VPCs exist in la-south-2?"
- "List subnets in la-south-2 for VPC vpc-xyz"
- "Show all OBS buckets"
- "List CBR backup vaults in la-south-2"
- "What backups exist in vault vault-123?"
- "Show Cloud Eye alarms in la-south-2"
- "List recent CTS audit traces"
- "What LTS log groups exist?"
- "Show my IAM projects"
```

## Security Notes

- **Read-only by default**: This server only exposes list/show tools. No create, update, delete, or restart operations.
- **No hardcoded credentials**: AK/SK are read exclusively from environment variables.
- **No credential exposure**: The `iam_get_current_user_or_projects` tool never returns AK/SK values.
- **Feature flag for write tools**: `ALLOW_HWC_WRITE_TOOLS` defaults to `false`. Any future write tools must check this flag and fail unless explicitly enabled.
- **SSL verification**: The Huawei Cloud SDK handles TLS. Ensure your environment trusts the Huawei Cloud CA certificates.

## Docker

### Build

```bash
docker build -t mcp-server-hwc-ops:dev -f huaweicloud_services_server/mcp_server_hwc_ops/Dockerfile .
```

### Run

```bash
docker run -d --name hwc-ops-mcp \
  -p 8888:8080 \
  -e HUAWEI_ACCESS_KEY="YOUR_AK" \
  -e HUAWEI_SECRET_KEY="YOUR_SK" \
  mcp-server-hwc-ops:dev
```

The MCP endpoint will be available at `http://localhost:8888/mcp/`.

### Docker Compose

```bash
# Create .env from the example
cp .env.example .env
# Edit .env with your credentials
vi .env

# Start
docker compose up -d
```

### OpenCode config with Docker

```json
{
  "mcpServers": {
    "hwc-ops": {
      "url": "http://localhost:8888/mcp/"
    }
  }
}
```

## Smoke Test

```bash
# Set credentials
export HUAWEI_ACCESS_KEY="your_ak"
export HUAWEI_SECRET_KEY="your_sk"

# Run in stdio mode and test with a simple JSON-RPC call
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | mcp-server-hwc-ops -t stdio

# Or start HTTP server and curl
mcp-server-hwc-ops -t http -p 8888 &
curl -X POST http://localhost:8888/mcp/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'

# Or with Docker
docker run -p 8888:8080 -e HUAWEI_ACCESS_KEY="ak" -e HUAWEI_SECRET_KEY="sk" mcp-server-hwc-ops:dev
curl -X POST http://localhost:8888/mcp/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

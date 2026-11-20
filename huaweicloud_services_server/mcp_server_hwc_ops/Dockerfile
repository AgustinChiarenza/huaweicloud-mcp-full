# ===================================
#
#   mcp-server-hwc-ops Docker image
#
# ===================================

# build stage
FROM python:3.12-slim AS build

WORKDIR /build

# Install uv for fast dependency resolution
RUN pip install --no-cache-dir uv

# Copy only the hwc_ops package
COPY huaweicloud_services_server/mcp_server_hwc_ops/ /build/hwc_ops_src/

# Create a standalone pyproject.toml for this package only
RUN cat > /build/pyproject.toml << 'PYPROJECT_EOF'
[build-system]
requires = ["setuptools"]
build-backend = "setuptools.build_meta"

[project]
name = "mcp-server-hwc-ops"
version = "0.1.0"
description = "Huawei Cloud Operations MCP Server"
requires-python = ">=3.10"
dependencies = [
    "fastmcp>=2.0.0",
    "pydantic>=2.0.0",
    "pyyaml>=6.0.2",
    "uvicorn>=0.30.0",
    "starlette>=0.40.0",
    "sse-starlette>=2.0.0",
    "huaweicloudsdkcore>=3.1.150",
    "huaweicloudsdkecs>=3.1.150",
    "huaweicloudsdkvpc>=3.1.150",
    "huaweicloudsdkcbr>=3.1.150",
    "huaweicloudsdkces>=3.1.150",
    "huaweicloudsdkcts>=3.1.150",
    "huaweicloudsdkiam>=3.1.150",
    "huaweicloudsdklts>=3.1.150",
    "huaweicloudsdkims>=3.1.150",
    "huaweicloudsdkevs>=3.1.150",
    "huaweicloudsdkeip>=3.1.150",
    "huaweicloudsdkelb>=3.1.150",
    "huaweicloudsdkdns>=3.1.150",
    "esdk-obs-python>=3.24.9",
]

[tool.setuptools]
packages = ["mcp_server_hwc_ops", "mcp_server_hwc_ops.config"]

[tool.setuptools.package-data]
"mcp_server_hwc_ops" = ["config/*.yaml"]

[project.scripts]
mcp-server-hwc-ops = "mcp_server_hwc_ops.run:main"
PYPROJECT_EOF

# Move source files into proper package layout
RUN mkdir -p /build/mcp_server_hwc_ops/config && \
    cp /build/hwc_ops_src/src/mcp_server_hwc_ops/server.py /build/mcp_server_hwc_ops/ && \
    cp /build/hwc_ops_src/src/mcp_server_hwc_ops/run.py /build/mcp_server_hwc_ops/ && \
    cp /build/hwc_ops_src/src/mcp_server_hwc_ops/config/config.yaml /build/mcp_server_hwc_ops/config/ && \
    touch /build/mcp_server_hwc_ops/__init__.py && \
    touch /build/mcp_server_hwc_ops/config/__init__.py

RUN uv pip install --system --no-cache-dir .

# runtime stage
FROM python:3.12-slim AS runtime

WORKDIR /app

# Copy installed packages and entrypoint from build
COPY --from=build /usr/local/lib/python3.12/site-packages/ /usr/local/lib/python3.12/site-packages/
COPY --from=build /usr/local/bin/mcp-server-hwc-ops /usr/local/bin/mcp-server-hwc-ops

# Non-root user
RUN groupadd -r mcp && useradd -r -g mcp mcp
USER mcp

EXPOSE 8080

ENTRYPOINT ["mcp-server-hwc-ops"]
CMD ["-t", "http", "-p", "8080"]

FROM python:3.12-slim

WORKDIR /app

# Dependencias del sistema mínimas.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Instalar el paquete con todos los servicios + BSS + multi-tenant.
COPY pyproject.toml ./
COPY assets ./assets
COPY huaweicloud_services_server ./huaweicloud_services_server
COPY huaweicloud_dws_mcp_inner ./huaweicloud_dws_mcp_inner
COPY huaweicloud_marketplace_server ./huaweicloud_marketplace_server
COPY common_servers ./common_servers

RUN pip install --no-cache-dir -e .

# El entry point por defecto es el server unificado (todos los servicios + BSS).
# Transporte y puerto se setean vía command en docker-compose.
ENTRYPOINT ["mcp-server-all"]
CMD ["-t", "http", "-p", "8080"]

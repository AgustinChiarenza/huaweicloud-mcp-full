# huaweicloud-mcp-full

> **MCP server unificado de Huawei Cloud** — catálogo completo de **~174 servicios** con mutaciones + **BSS billing/costos** + **multi-tenant** + **Terraform Registry**.

Fusión de dos repos MCP de Huawei Cloud:
- **[`huaweicloud-mcp`](https://github.com/AgustinChiarenza/huaweicloud-mcp)**: motor genérico + ~174 servicios con mutaciones (crear/borrar ECS, VPCs, discos, RDS, CCE, KMS, etc.).
- **[`mcp-huawei-cloud`](https://github.com/AgustinChiarenza/mcp-huawei-cloud)**: BSS billing, multi-tenant por headers HTTP, y servidor Terraform.

---

## ✨ Qué tiene

| Capacidad | Origen | Descripción |
|---|---|---|
| **~174 servicios, mutaciones** | huaweicloud-mcp | Control total del cloud: ECS, VPC, EIP, EVS, IMS, ELB, DNS, CBR, OBS, CES, CTS, LTS, IAM, RDS, DDS, GaussDB, CCE, SWR, KMS, WAF, HSS, ModelArts, OCR, DCS, Kafka, APIG, DWS, DLI, SMS, y ~150 más. |
| **BSS billing** | mcp-huawei-cloud | `bss_total_cost`, `bss_cycle_breakdown`, `bss_list_resource_records` — costos por ciclo, por servicio y por recurso. Cache en memoria + disco para ciclos cerrados. |
| **Multi-tenant** | mcp-huawei-cloud | Credenciales por request vía headers `X-Huawei-Access-Key` / `X-Huawei-Secret-Key` / `X-Huawei-Region`. El contenedor no guarda secrets. |
| **Terraform Registry** | mcp-huawei-cloud | Server Go para lookups de módulos, providers y versiones públicas de Terraform. |

---

## 🚀 Quick start

### Docker Compose (recomendado)

```bash
cp .env.example .env
# editá .env con tu AK/SK (o dejalo vacío para multi-tenant)
docker compose up -d --build
```

- **hwc-mcp-all**: `http://localhost:8888/mcp` — todos los servicios + BSS
- **terraform-mcp**: `http://localhost:8088/mcp` — Terraform Registry

### Local (Python)

```bash
pip install -e .
mcp-server-all -t http -p 8888   # server unificado (todo + BSS)
mcp-server-ecs -t stdio          # un servicio individual
mcp-server-bss -t http -p 8889   # solo billing
```

---

## 🔑 Credenciales

### Single-tenant (simple)

Seteá variables de entorno:
```bash
export HUAWEI_ACCESS_KEY=...
export HUAWEI_SECRET_KEY=...
export HUAWEI_REGION=la-south-2
```

### Multi-tenant (multi-cuenta, seguro)

Activá el modo por-request y mandá las creds en headers HTTP de cada request MCP:
```bash
export HWC_REQUIRE_PER_REQUEST_CREDS=1
```

Headers:
| Header | Descripción |
|---|---|
| `X-Huawei-Access-Key` | AK de la cuenta del usuario |
| `X-Huawei-Secret-Key` | SK de la cuenta del usuario |
| `X-Huawei-Region` | Region (opcional, override por-request) |

Con `HWC_REQUIRE_PER_REQUEST_CREDS=1`, un request sin headers **falla** (no cae a las creds del entorno). Esto evita que se devuelvan datos de la cuenta equivocada.

---

## 🧰 Tools de billing (BSS)

| Tool | Uso |
|---|---|
| `bss_total_cost(cycle?)` | Total facturado del ciclo + breakdown por servicio. **Default para "cuánto gasté"**. |
| `bss_cycle_breakdown(cycle?)` | Detalle por recurso (incluye recursos dados de baja). Para "qué recurso me cuesta más". |
| `bss_list_resource_records(cycle?, cloud_service_type?, limit?)` | Fee-records crudos. |

`cycle` = `YYYY-MM` (default: mes actual). BSS es global (region `ap-southeast-1`).

---

## 🏗️ Arquitectura

```
huaweicloud-mcp-full/
├── assets/utils/
│   ├── server.py              # Motor MCP (OpenAPI → tools) + middleware multi-tenant
│   ├── hwc_tools.py           # Cliente Huawei Cloud (BasicCredentials)
│   ├── per_request_creds.py   # Multi-tenant: creds por header (ContextVar)
│   ├── bss_tools.py           # BSS billing (GlobalCredentials) + cache
│   └── openapi.py             # OpenAPI spec → MCP tools
├── huaweicloud_services_server/
│   ├── mcp_server_ecs/        # 174 servicios individuales (entry points)
│   ├── mcp_server_vpc/
│   ├── ...
│   ├── mcp_server_bss/        # Server standalone de billing
│   └── mcp_server_all/        # Server unificado (todo + BSS en un endpoint)
├── terraform-mcp/             # Server Go (imagen SWR) — Terraform Registry
├── docker-compose.yml         # hwc-mcp-all + terraform-mcp
├── Dockerfile                 # Build del server unificado
└── pyproject.toml
```

### Entry points

| Command | Qué hace |
|---|---|
| `mcp-server-all` | **Server unificado**: los 174 servicios + BSS en un solo endpoint (necesario para multi-tenant por header). Tools namespacedeas: `ecs__list_servers`, `vpc__list_vpcs`, etc. |
| `mcp-server-ecs` (etc.) | Server individual de un servicio. Útil cuando no necesitás multi-tenant o solo un servicio. |
| `mcp-server-bss` | Server standalone de billing (solo las 3 tools BSS). |

---

## 📦 Servicios incluidos (~174)

**Networking**: ELB, VPC, EIP, NAT, VPCEP, CC, ER, GA, DC, VPN
**Compute**: ECS, AS, FunctionGraph, IMS, BMS, DeH
**Storage**: EVS, CBR, SFS Turbo, OBS
**Databases**: DDS, RDS, TaurusDB, GaussDB, GeminiDB, DRS, DDM, DAS, UGO
**Containers**: CCE, SWR, ASM, AOS, CCI
**AI**: OCR, FRS, ModelArts, Image, ImageSearch, Moderation, SIS, GES, CBS, Octopus
**CodeArts**: CPTS, ServiceStage, CodeCheck, ProjectMan, CodeHub, CloudBuild, CloudTest, Deploy/Pipeline/Artifact, CAE
**Middleware**: DCS, Kafka, CSE, RocketMQ, RabbitMQ, APIG, APM
**Analytics**: MRS, DWS, DLI, DataArtsStudio, CSS, DIS
**Management**: IAM, CES, LTS, RMS, CTS, TMS, EPS, SMN, AOM, Organizations, RAM, Config, RFS, STS, COC, RGC
**Security**: HSS, KPS, CSMS, KMS, CCM, SCM, Anti-DDoS, DBSS, WAF, DSC, CFW, CBH, EdgeSec, SecMaster, AAD
**Migration**: SMS, OMS, CDM
**Media**: MPC, Live, VOD, CloudRTC
**Business**: ROMA, DNS, Meeting, Workspace
**IoT**: IoTDA, GSL, IoTDM
**Billing**: BSS (BSSINTL)

---

## License

Apache-2.0 / MIT (ver LICENSE).

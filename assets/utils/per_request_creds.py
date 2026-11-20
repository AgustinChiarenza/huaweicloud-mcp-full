"""Credenciales por request para el MCP de Huawei Cloud (multi-tenant).

Adaptado de mcp-huawei-cloud/per_request_creds.py al motor de huaweicloud-mcp,
que usa ``mcp.server.Server`` + Starlette (no FastMCP). En lugar de
``fastmcp.server.dependencies.get_http_headers`` usamos un
``contextvars.ContextVar`` poblado por middleware de Starlette en
``assets/utils/server.py``.

**El problema.** El contenedor arranca con UNA AK/SK en el entorno y todas las
tools responden sobre esa cuenta. En un deploy multi-usuario eso significa que
cualquiera que pregunte "qué ECS tengo" o "cuánto gasté" recibe la infra y los
costos del operador.

**La solución.** La app manda las credenciales del usuario en headers HTTP del
request MCP y acá las preferimos. El contenedor deja de tener una cuenta propia:
pasa a ser stateless respecto de las credenciales.

**Fallo ruidoso, no silencioso.** Si no se pueden leer los headers (transporte
no-HTTP, request sin contexto), el default es caer a las credenciales del
entorno. Con ``HWC_REQUIRE_PER_REQUEST_CREDS=1`` ese fallback se convierte en
error: preferimos que el tool falle a que devuelva datos de otra cuenta sin
avisar.
"""
from __future__ import annotations

import contextvars
import hashlib
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

AK_HEADER = "x-huawei-access-key"
SK_HEADER = "x-huawei-secret-key"
REGION_HEADER = "x-huawei-region"

REQUIRE_PER_REQUEST = os.environ.get("HWC_REQUIRE_PER_REQUEST_CREDS", "0") == "1"

# ContextVar poblado por el middleware de Starlette en server.py.
# Contiene un dict de headers en minúscula, o None si no hay contexto HTTP.
_request_headers: contextvars.ContextVar[Optional[dict[str, str]]] = contextvars.ContextVar(
    "hwc_request_headers", default=None
)


class MissingRequestCredentials(RuntimeError):
    """No llegaron credenciales en el request y el fallback está prohibido."""


def set_request_headers(headers: dict[str, str]) -> contextvars.Token:
    """Poblar los headers del request en curso. Llamar desde middleware ASGI.

    Devuelve un token para restaurar (``reset_request_headers``).
    """
    normalized = {str(k).lower(): str(v) for k, v in (headers or {}).items()}
    return _request_headers.set(normalized)


def reset_request_headers(token: contextvars.Token) -> None:
    _request_headers.reset(token)


def _http_headers() -> dict[str, str]:
    """Headers del request MCP en curso, en minúscula. {} si no hay contexto."""
    return _request_headers.get() or {}


def request_credentials() -> Optional[tuple[str, str]]:
    """(ak, sk) del request en curso, o None si no vinieron."""
    headers = _http_headers()
    ak = (headers.get(AK_HEADER) or "").strip()
    sk = (headers.get(SK_HEADER) or "").strip()
    return (ak, sk) if ak and sk else None


def request_region() -> Optional[str]:
    return (_http_headers().get(REGION_HEADER) or "").strip() or None


def account_fingerprint() -> str:
    """Huella estable y no reversible de la cuenta del request.

    Los caches del MCP DEBEN incluirla: sirviendo varias cuentas, una key sin
    dimensión de cuenta le entrega la factura de un tenant al siguiente.
    """
    creds = request_credentials()
    ak = creds[0] if creds else os.environ.get("HUAWEI_ACCESS_KEY", "")
    if not ak:
        return "noaccount"
    return hashlib.sha256(ak.encode("utf-8")).hexdigest()[:16]


def resolve_credentials(fallback_ak: str = "", fallback_sk: str = "") -> tuple[str, str]:
    """Resolver de creds unificado: per-request > env > fallback.

    Usar este helper desde call_tool y bss_tools. Respeta
    ``HWC_REQUIRE_PER_REQUEST_CREDS``.
    """
    creds = request_credentials()
    if creds is not None:
        return creds

    env_ak = os.environ.get("HUAWEI_ACCESS_KEY") or os.environ.get("HUAWEICLOUD_SDK_AK", "")
    env_sk = os.environ.get("HUAWEI_SECRET_KEY") or os.environ.get("HUAWEICLOUD_SDK_SK", "")
    ak = fallback_ak or env_ak
    sk = fallback_sk or env_sk

    if not ak or not sk:
        if REQUIRE_PER_REQUEST:
            raise MissingRequestCredentials(
                "El request no trae credenciales Huawei (headers "
                "X-Huawei-Access-Key / X-Huawei-Secret-Key) y "
                "HWC_REQUIRE_PER_REQUEST_CREDS=1 prohíbe usar las del entorno. "
                "Se corta acá para no responder con la cuenta equivocada."
            )
    return (ak, sk)

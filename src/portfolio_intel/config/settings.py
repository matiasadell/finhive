"""Configuración central: modelo LLM, backend de datos, Unity Catalog.

Todo el resto del paquete importa `get_chat_model` y `get_data_backend` desde
acá en vez de leer env vars o instanciar `ChatDatabricks` directamente, para
que el tiering de modelos y la elección de backend de datos sean una única
decisión centralizada -- mismo criterio que `finhive.config.settings`.
"""

from __future__ import annotations

import os
from typing import Literal

from dotenv import load_dotenv

load_dotenv()

# --- Unity Catalog (solo aplica con PORTFOLIO_INTEL_DATA_BACKEND=databricks) ---
UC_CATALOG = "workspace"
UC_SCHEMA = "portfolio_intel"
UC_FULL_SCHEMA = f"{UC_CATALOG}.{UC_SCHEMA}"
UC_TABLE_USE_CASE_INVENTORY = "rua_use_case_inventory"
UC_TABLE_USE_CASE_DETAIL = "ai_use_case_detail"

# --- Foundation Model APIs nativos de Databricks (mismo par que finhive) ---
SUPERVISOR_MODEL_ENDPOINT = "databricks-meta-llama-3-3-70b-instruct"
WORKER_MODEL_ENDPOINT = "databricks-meta-llama-3-1-8b-instruct"


def get_data_backend() -> Literal["local", "databricks"]:
    """Lee `PORTFOLIO_INTEL_DATA_BACKEND` de env; default `"local"`.

    Esta es la única decisión que separa correr en esta máquina de desarrollo
    (sin acceso a Databricks, ver `prompts/constraints_environment.md`) de
    correr en la compu de trabajo contra las tablas Delta reales -- todo lo
    demás (tools, agentes, grafo) usa `data.store.load_portfolio_data()` sin
    saber cuál de los dos está activo.
    """
    value = os.getenv("PORTFOLIO_INTEL_DATA_BACKEND", "local").strip().lower()
    if value not in ("local", "databricks"):
        raise RuntimeError(
            f"PORTFOLIO_INTEL_DATA_BACKEND='{value}' inválido -- tiene que ser "
            "'local' o 'databricks'."
        )
    return value  # type: ignore[return-value]


def get_databricks_host() -> str:
    """Lee DATABRICKS_HOST de env; falla explícito si no está configurada."""
    host = os.getenv("DATABRICKS_HOST", "").strip()
    if not host:
        raise RuntimeError(
            "DATABRICKS_HOST no está seteada. Es la URL de tu workspace "
            "(ej. https://dbc-xxxxxxxx-xxxx.cloud.databricks.com)."
        )
    return host


def get_databricks_token() -> str:
    """Lee DATABRICKS_TOKEN de env; falla explícito si no está configurada."""
    token = os.getenv("DATABRICKS_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "DATABRICKS_TOKEN no está seteada. Generá un Personal Access "
            "Token con `databricks tokens create` y ponelo en tu .env."
        )
    return token


def get_sql_warehouse_id() -> str:
    """Lee SQL_WAREHOUSE_ID de env; falla explícito si no está configurada.

    Solo hace falta con `PORTFOLIO_INTEL_DATA_BACKEND=databricks` -- el
    backend local (default, usado en esta máquina de desarrollo) nunca la
    necesita.
    """
    warehouse_id = os.getenv("SQL_WAREHOUSE_ID", "").strip()
    if not warehouse_id:
        raise RuntimeError(
            "SQL_WAREHOUSE_ID no está seteada -- necesaria para el backend "
            "'databricks' del data store. No hace falta con el backend "
            "'local' (default)."
        )
    return warehouse_id


def get_chat_model(tier: Literal["supervisor", "worker"], temperature: float = 0.1):
    """Instancia un `ChatDatabricks` apuntando al endpoint correcto según el rol.

    Args:
        tier: "supervisor" para el top-level supervisor (routing, requiere más
            capacidad de razonamiento); "worker" para los agentes de dominio
            (tool-calling sobre las tools deterministas de `tools/`).
        temperature: temperatura de muestreo, baja por default para
            recomendaciones consistentes.

    Esta llamada solo funciona con conexión real a Databricks -- en esta
    máquina de desarrollo (ver `prompts/constraints_environment.md`) va a
    fallar al invocar el modelo, no al construir el cliente; eso es esperado,
    no un bug a perseguir acá.
    """
    from databricks_langchain import ChatDatabricks

    endpoint = SUPERVISOR_MODEL_ENDPOINT if tier == "supervisor" else WORKER_MODEL_ENDPOINT
    return ChatDatabricks(endpoint=endpoint, temperature=temperature)

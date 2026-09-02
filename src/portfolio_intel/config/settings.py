from __future__ import annotations

import os
from typing import Literal

from dotenv import load_dotenv

load_dotenv()

UC_CATALOG = "workspace"
UC_SCHEMA = "portfolio_intel"
UC_FULL_SCHEMA = f"{UC_CATALOG}.{UC_SCHEMA}"
UC_TABLE_USE_CASE_INVENTORY = "rua_use_case_inventory"
UC_TABLE_USE_CASE_DETAIL = "ai_use_case_detail"

SUPERVISOR_MODEL_ENDPOINT = "databricks-meta-llama-3-3-70b-instruct"
WORKER_MODEL_ENDPOINT = "databricks-meta-llama-3-1-8b-instruct"

# Scope real (ver infra/databricks/setup_secrets.py). Databricks solo deja leer
# un secret vía el `dbutils` ambiente de un notebook/serving endpoint, no
# remoto -- por eso estas funciones siguen leyendo env vars: en un notebook esa
# env var se setea con dbutils.secrets.get(SECRET_SCOPE, ...) primero; en
# serving, Databricks resuelve las refs `{{secrets/...}}` de deploy_agent.py
# antes de arrancar el contenedor. Acá (sin ninguna de las dos cosas) se lee de .env.
SECRET_SCOPE = "portfolio_intel"


def get_data_backend() -> Literal["local", "databricks"]:
    value = os.getenv("PORTFOLIO_INTEL_DATA_BACKEND", "local").strip().lower()
    if value not in ("local", "databricks"):
        raise RuntimeError(
            f"PORTFOLIO_INTEL_DATA_BACKEND='{value}' inválido -- tiene que ser "
            "'local' o 'databricks'."
        )
    return value  # type: ignore[return-value]


def get_databricks_host() -> str:
    host = os.getenv("DATABRICKS_HOST", "").strip()
    if not host:
        raise RuntimeError(
            "DATABRICKS_HOST no está seteada -- en Databricks viene del secret "
            f"{SECRET_SCOPE}/databricks_host (ver infra/databricks/setup_secrets.py), "
            "en esta máquina va en .env."
        )
    return host


def get_databricks_token() -> str:
    token = os.getenv("DATABRICKS_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "DATABRICKS_TOKEN no está seteada -- en Databricks viene del secret "
            f"{SECRET_SCOPE}/databricks_token (ver infra/databricks/setup_secrets.py), "
            "en esta máquina va en .env."
        )
    return token


def get_sql_warehouse_id() -> str:
    warehouse_id = os.getenv("SQL_WAREHOUSE_ID", "").strip()
    if not warehouse_id:
        raise RuntimeError(
            "SQL_WAREHOUSE_ID no está seteada -- en Databricks viene del secret "
            f"{SECRET_SCOPE}/sql_warehouse_id (ver infra/databricks/setup_secrets.py), "
            "en esta máquina va en .env."
        )
    return warehouse_id


def get_databricks_workspace_email() -> str:
    from databricks.sdk import WorkspaceClient

    return WorkspaceClient().current_user.me().user_name


def get_chat_model(tier: Literal["supervisor", "worker"], temperature: float = 0.1):
    from databricks_langchain import ChatDatabricks

    endpoint = SUPERVISOR_MODEL_ENDPOINT if tier == "supervisor" else WORKER_MODEL_ENDPOINT
    return ChatDatabricks(endpoint=endpoint, temperature=temperature)

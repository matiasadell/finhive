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
            "DATABRICKS_HOST no está seteada. Es la URL de tu workspace "
            "(ej. https://dbc-xxxxxxxx-xxxx.cloud.databricks.com)."
        )
    return host


def get_databricks_token() -> str:
    token = os.getenv("DATABRICKS_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "DATABRICKS_TOKEN no está seteada. Generá un Personal Access "
            "Token con `databricks tokens create` y ponelo en tu .env."
        )
    return token


def get_sql_warehouse_id() -> str:
    warehouse_id = os.getenv("SQL_WAREHOUSE_ID", "").strip()
    if not warehouse_id:
        raise RuntimeError(
            "SQL_WAREHOUSE_ID no está seteada -- necesaria para el backend "
            "'databricks' del data store. No hace falta con el backend "
            "'local' (default)."
        )
    return warehouse_id


def get_databricks_workspace_email() -> str:
    from databricks.sdk import WorkspaceClient

    return WorkspaceClient().current_user.me().user_name


def get_chat_model(tier: Literal["supervisor", "worker"], temperature: float = 0.1):
    from databricks_langchain import ChatDatabricks

    endpoint = SUPERVISOR_MODEL_ENDPOINT if tier == "supervisor" else WORKER_MODEL_ENDPOINT
    return ChatDatabricks(endpoint=endpoint, temperature=temperature)

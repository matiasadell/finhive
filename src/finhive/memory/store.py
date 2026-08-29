"""Ejecución de SQL contra el SQL warehouse serverless ya provisionado.

Backend real de la memoria persistente: tablas Delta en `workspace.finhive`,
no Lakebase Postgres (ver ADR 0012 — Public Preview, sin confirmar si Free
Edition lo habilita gratis; el warehouse serverless, en cambio, ya está
verificado en $0 y provisionado desde el arranque del proyecto). Usa
`databricks.sdk.WorkspaceClient` sin argumentos explícitos — mismo patrón de
auth ambiente (`DATABRICKS_CONFIG_PROFILE`, OAuth vía CLI) que ya usa
`infra/databricks/register_uc_functions.py`.
"""

from __future__ import annotations

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementParameterListItem, StatementState

from finhive.config.settings import SQL_WAREHOUSE_ID, UC_CATALOG, UC_SCHEMA

_client: WorkspaceClient | None = None


def _get_client() -> WorkspaceClient:
    global _client
    if _client is None:
        _client = WorkspaceClient()
    return _client


def execute_sql(statement: str, params: dict[str, str] | None = None) -> list[list[str]]:
    """Corre una sentencia SQL contra el warehouse serverless; devuelve filas como strings.

    Los valores ya vienen como `str` desde la Statement Execution API — quien
    llama castea (int, float, etc.) si hace falta. `params` se manda como
    parámetros nombrados (`:nombre` en el SQL), no interpolados en el string,
    para no exponer las tablas de memoria a inyección SQL.
    """
    parameters = (
        [StatementParameterListItem(name=k, value=v) for k, v in params.items()]
        if params
        else None
    )
    response = _get_client().statement_execution.execute_statement(
        statement=statement,
        warehouse_id=SQL_WAREHOUSE_ID,
        catalog=UC_CATALOG,
        schema=UC_SCHEMA,
        wait_timeout="30s",
        parameters=parameters,
    )
    if response.status and response.status.state == StatementState.FAILED:
        raise RuntimeError(f"statement SQL falló: {response.status.error}")
    if response.result and response.result.data_array:
        return response.result.data_array
    return []

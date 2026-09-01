"""Crea el schema y las 2 tablas Delta de Portfolio Intel en Unity Catalog (idempotente).

Sin esto, `DatabricksDeltaStore` (`data/store.py`, ver ADR 0003) no tiene
nada que leer -- este es el "próximo paso real" que quedó pendiente en ADR
0007 para poder desplegar el agente de verdad contra Databricks.

No se puede correr desde esta máquina de desarrollo (sin conexión a
Databricks, ver `prompts/constraints_environment.md`) -- escrito para
correr en la compu de trabajo o desde un notebook de Databricks, igual que
`deploy_agent.py`.

Carga los CSVs sintéticos de `data/sample_docs/` tal cual (mismo esquema
exacto que espera un CSV real, ver `data/schema.py`) -- si en algún momento
se reemplazan por datos reales de la empresa con el mismo nombre de archivo
y esquema, este script no necesita ningún cambio.

Uso (desde la raíz del repo, en un notebook/entorno con conexión real):
    python infra/databricks/setup_catalog.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import pandas as pd

from portfolio_intel.config.settings import (
    UC_CATALOG,
    UC_FULL_SCHEMA,
    UC_SCHEMA,
    UC_TABLE_USE_CASE_DETAIL,
    UC_TABLE_USE_CASE_INVENTORY,
    get_sql_warehouse_id,
)
from portfolio_intel.data.schema import RUAI_USE_CASE_COLUMNS, USE_CASE_DETAIL_COLUMNS

_SAMPLE_DOCS_DIR = Path(__file__).resolve().parents[2] / "data" / "sample_docs"

# Columnas que son numéricas/fecha en el esquema real -- todo lo que no está
# acá se crea como STRING. Ver `data/schema.py` para el esquema completo;
# esta lista es deliberadamente chica (solo las columnas que
# `tools/*.py` de verdad usa como número/fecha).
_NUMERIC_COLUMNS = {
    "count",
    "max impact",
    "min impact",
    "planned investment",
    "projected total investment",
    "planned opex",
}
_DATE_COLUMNS = {
    "use case submission date",
    "value return begins in",
    "value return plateaus in",
}


def _sql_type(column: str) -> str:
    if column in _NUMERIC_COLUMNS:
        return "DOUBLE"
    if column in _DATE_COLUMNS:
        return "DATE"
    return "STRING"


def _quoted_column(column: str) -> str:
    # Backticks: varias columnas del esquema real tienen espacios
    # ("use case id", "max impact", ...) -- sin backticks, Delta las
    # interpreta como varios tokens SQL y el DDL falla.
    return f"`{column}`"


def _create_table_ddl(table: str, columns: list[str]) -> str:
    column_defs = ",\n    ".join(f"{_quoted_column(c)} {_sql_type(c)}" for c in columns)
    return f"CREATE TABLE IF NOT EXISTS {UC_FULL_SCHEMA}.{table} (\n    {column_defs}\n)"


def _sql_literal(value, column: str) -> str:
    if pd.isna(value):
        return "NULL"
    if column in _NUMERIC_COLUMNS:
        return str(value)
    if column in _DATE_COLUMNS:
        return f"DATE'{value}'"
    escaped = str(value).replace("'", "''")
    return f"'{escaped}'"


def _insert_statement(table: str, columns: list[str], df: pd.DataFrame) -> str:
    column_list = ", ".join(_quoted_column(c) for c in columns)
    value_rows = []
    for _, row in df.iterrows():
        values = ", ".join(_sql_literal(row[c], c) for c in columns)
        value_rows.append(f"({values})")
    return f"INSERT INTO {UC_FULL_SCHEMA}.{table} ({column_list}) VALUES\n" + ",\n".join(value_rows)


def main() -> None:
    from databricks.sdk import WorkspaceClient
    from databricks.sdk.service.sql import StatementState

    client = WorkspaceClient()
    warehouse_id = get_sql_warehouse_id()

    def run(statement: str) -> None:
        response = client.statement_execution.execute_statement(
            statement=statement, warehouse_id=warehouse_id, wait_timeout="30s"
        )
        if response.status and response.status.state == StatementState.FAILED:
            raise RuntimeError(f"statement SQL falló: {response.status.error}\n{statement[:500]}")

    run(f"CREATE SCHEMA IF NOT EXISTS {UC_CATALOG}.{UC_SCHEMA}")
    print(f"schema listo: {UC_FULL_SCHEMA}")

    run(_create_table_ddl(UC_TABLE_USE_CASE_INVENTORY, RUAI_USE_CASE_COLUMNS))
    print(f"tabla lista: {UC_FULL_SCHEMA}.{UC_TABLE_USE_CASE_INVENTORY}")
    run(_create_table_ddl(UC_TABLE_USE_CASE_DETAIL, USE_CASE_DETAIL_COLUMNS))
    print(f"tabla lista: {UC_FULL_SCHEMA}.{UC_TABLE_USE_CASE_DETAIL}")

    ruai_path = _SAMPLE_DOCS_DIR / "rua_use_case_inventory.csv"
    detail_path = _SAMPLE_DOCS_DIR / "ai_use_case_detail.csv"
    if not ruai_path.exists() or not detail_path.exists():
        print(
            "No hay CSVs en data/sample_docs/ para cargar -- corré "
            "`python -m portfolio_intel.data.synthetic` primero si querés "
            "cargar el dataset sintético. Las tablas quedaron creadas, "
            "vacías."
        )
        return

    # Idempotente: TRUNCATE + re-insert, no un simple INSERT -- correr esto
    # dos veces no debería duplicar filas.
    run(f"TRUNCATE TABLE {UC_FULL_SCHEMA}.{UC_TABLE_USE_CASE_INVENTORY}")
    run(_insert_statement(UC_TABLE_USE_CASE_INVENTORY, RUAI_USE_CASE_COLUMNS, pd.read_csv(ruai_path)))
    print(f"datos cargados: {UC_FULL_SCHEMA}.{UC_TABLE_USE_CASE_INVENTORY}")

    run(f"TRUNCATE TABLE {UC_FULL_SCHEMA}.{UC_TABLE_USE_CASE_DETAIL}")
    run(_insert_statement(UC_TABLE_USE_CASE_DETAIL, USE_CASE_DETAIL_COLUMNS, pd.read_csv(detail_path)))
    print(f"datos cargados: {UC_FULL_SCHEMA}.{UC_TABLE_USE_CASE_DETAIL}")


if __name__ == "__main__":
    main()

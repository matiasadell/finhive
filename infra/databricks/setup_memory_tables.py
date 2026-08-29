"""Crea las tablas Delta de memoria persistente en `workspace.finhive` (idempotente).

Uso:
    uv run python infra/databricks/setup_memory_tables.py

Ver ADR 0012 para por qué son tablas Delta vía el SQL warehouse serverless ya
provisionado (`Serverless Starter Warehouse`), y no Lakebase Postgres (Public
Preview, entitlement de Free Edition sin verificar).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from finhive.config.settings import UC_FULL_SCHEMA
from finhive.memory.store import execute_sql

_CREATE_SESSIONS = f"""
CREATE TABLE IF NOT EXISTS {UC_FULL_SCHEMA}.conversation_sessions (
    thread_id STRING,
    turn_index INT,
    role STRING,
    msg_name STRING,
    content STRING,
    created_at TIMESTAMP
)
"""

_CREATE_FACTS = f"""
CREATE TABLE IF NOT EXISTS {UC_FULL_SCHEMA}.conversation_facts (
    thread_id STRING,
    fact STRING,
    created_at TIMESTAMP
)
"""


def main() -> None:
    execute_sql(_CREATE_SESSIONS)
    print(f"tabla lista: {UC_FULL_SCHEMA}.conversation_sessions")
    execute_sql(_CREATE_FACTS)
    print(f"tabla lista: {UC_FULL_SCHEMA}.conversation_facts")


if __name__ == "__main__":
    main()

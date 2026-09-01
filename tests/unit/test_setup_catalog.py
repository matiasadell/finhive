"""`infra/databricks/setup_catalog.py` -- solo la generación de SQL, sin ejecutar nada.

No hay conexión a Databricks en esta máquina (ver
`prompts/constraints_environment.md`), así que esto no puede probar que el
DDL/INSERT corren de verdad -- prueba que el SQL que se generaría contra el
dataset real es válido: columnas correctas, tipos correctos, escaping de
comillas, `NULL`s, y ninguna fila perdida.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "infra" / "databricks"))

from portfolio_intel.data.schema import RUAI_USE_CASE_COLUMNS, USE_CASE_DETAIL_COLUMNS

setup_catalog = pytest.importorskip("setup_catalog")


def test_create_table_ddl_quotes_columns_with_spaces():
    ddl = setup_catalog._create_table_ddl("rua_use_case_inventory", RUAI_USE_CASE_COLUMNS)
    assert "`use case id`" in ddl
    assert "`AI Use Case Name`" in ddl
    assert ddl.count("`") == len(RUAI_USE_CASE_COLUMNS) * 2


def test_numeric_and_date_columns_typed_correctly():
    ddl = setup_catalog._create_table_ddl("ai_use_case_detail", USE_CASE_DETAIL_COLUMNS)
    assert "`max impact` DOUBLE" in ddl
    assert "`use case submission date` DATE" in ddl
    assert "`business challenge` STRING" in ddl


def test_insert_statement_has_one_row_per_use_case(use_cases_df):
    stmt = setup_catalog._insert_statement(
        "rua_use_case_inventory", RUAI_USE_CASE_COLUMNS, use_cases_df
    )
    assert stmt.count("\n(") == len(use_cases_df)  # una fila "(...)" por caso de uso


def test_null_barrier_renders_as_sql_null(use_cases_df):
    stmt = setup_catalog._insert_statement(
        "ai_use_case_detail", USE_CASE_DETAIL_COLUMNS, use_cases_df
    )
    # UC-001 (scale tier) no tiene barrera documentada -- la celda vacía del
    # CSV llega como NaN vía pandas, tiene que renderizar como NULL, no como
    # el string literal "nan" (mismo bug real que ya se encontró y arregló
    # en value_realization_tools -- ver Tasks 5-8).
    assert ", NULL, 'High'" in stmt


def test_text_with_apostrophe_is_escaped():
    df = pd.DataFrame({"title": ["Bob's Use Case"]})
    literal = setup_catalog._sql_literal("Bob's Use Case", "title")
    assert literal == "'Bob''s Use Case'"

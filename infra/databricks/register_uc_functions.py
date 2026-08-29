"""Registra funciones Python como Unity Catalog Functions (tools gobernadas).

Genérico y reutilizable entre dominios: cada dominio expone su lista de
funciones de tools, y este script las registra (o actualiza, `replace=True`
lo hace idempotente) en `workspace.finhive`. Ver ADR 0004 para por qué se usa
este patrón en vez de los Managed MCP servers de Databricks.

Uso:
    uv run python infra/databricks/register_uc_functions.py
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from finhive.config.settings import UC_CATALOG, UC_SCHEMA


def register_functions(functions: list[Callable]) -> None:
    """Registra cada función en Unity Catalog, imprimiendo el nombre completo."""
    from unitycatalog.ai.core.databricks import DatabricksFunctionClient

    client = DatabricksFunctionClient()
    for func in functions:
        info = client.create_python_function(
            func=func,
            catalog=UC_CATALOG,
            schema=UC_SCHEMA,
            replace=True,
        )
        print(f"registrada: {info.full_name}")


def main() -> None:
    from finhive.tools.macro_data import (
        get_fred_series_history,
        get_fred_series_latest,
        search_fred_series,
    )

    register_functions([search_fred_series, get_fred_series_latest, get_fred_series_history])


if __name__ == "__main__":
    main()

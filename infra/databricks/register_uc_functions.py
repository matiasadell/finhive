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
    from finhive.tools.crypto_data import (
        get_crypto_price,
        get_crypto_price_history,
        get_top_crypto_by_market_cap,
        get_trending_crypto,
        search_crypto_id,
    )
    from finhive.tools.equity_data import (
        calculate_sma,
        get_sec_company_facts,
        get_stock_fundamentals,
        get_stock_price_history,
        get_stock_quote,
        search_filing_content,
        search_sec_filings,
    )
    from finhive.tools.macro_data import (
        get_fred_series_history,
        get_fred_series_latest,
        search_fred_series,
    )
    from finhive.tools.news_data import (
        get_earnings_calendar,
        get_market_news_sentiment,
        get_stock_news_sentiment,
        web_search_news,
    )
    from finhive.tools.portfolio_math import (
        add_numbers,
        calculate_correlation_matrix,
        calculate_portfolio_var,
        calculate_portfolio_volatility,
        calculate_sharpe_ratio,
        divide_numbers,
        multiply_numbers,
    )

    register_functions(
        [
            search_fred_series,
            get_fred_series_latest,
            get_fred_series_history,
            get_stock_quote,
            get_stock_fundamentals,
            get_stock_price_history,
            calculate_sma,
            search_sec_filings,
            get_sec_company_facts,
            search_filing_content,
            calculate_portfolio_volatility,
            calculate_portfolio_var,
            calculate_correlation_matrix,
            calculate_sharpe_ratio,
            add_numbers,
            multiply_numbers,
            divide_numbers,
            get_stock_news_sentiment,
            get_market_news_sentiment,
            get_earnings_calendar,
            web_search_news,
            search_crypto_id,
            get_crypto_price,
            get_crypto_price_history,
            get_trending_crypto,
            get_top_crypto_by_market_cap,
        ]
    )


if __name__ == "__main__":
    main()

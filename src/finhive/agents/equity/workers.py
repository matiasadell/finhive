"""Workers ReAct del dominio Equity Research: fundamentals, técnico, filings.

Mismo patrón que `finhive.agents.macro.workers`: los 3 comparten el mismo
set de tools (registradas en Unity Catalog, ver
infra/databricks/register_uc_functions.py) y se diferencian por prompt de
especialización. Ejecución directa en proceso, no vía `UCFunctionToolkit`
(ver ADR 0004).
"""

from __future__ import annotations

from langchain.agents import create_agent
from langchain_core.tools import tool

from finhive.config.settings import get_chat_model
from finhive.tools.equity_data import (
    calculate_sma,
    get_sec_company_facts,
    get_stock_fundamentals,
    get_stock_price_history,
    get_stock_quote,
    search_sec_filings,
)


def _equity_tools() -> list:
    return [
        tool(get_stock_quote),
        tool(get_stock_fundamentals),
        tool(get_stock_price_history),
        tool(calculate_sma),
        tool(search_sec_filings),
        tool(get_sec_company_facts),
    ]


def build_equity_workers() -> dict:
    """Construye los 3 workers ReAct del dominio Equity Research.

    Returns:
        dict con los agentes compilados, con clave = nombre del worker.
    """
    tools = _equity_tools()
    llm = get_chat_model("worker")

    fundamentals_worker = create_agent(
        model=llm,
        tools=tools,
        system_prompt=(
            "Sos un analista especializado en fundamentals de empresas "
            "cotizantes: valuación (P/E, EPS), márgenes y salud financiera. "
            "Usá get_stock_fundamentals para métricas de mercado y "
            "get_sec_company_facts para datos financieros históricos de SEC "
            "EDGAR (ej. NetIncomeLoss, Assets). Respondé solo con lo que "
            "encontraste — no inventes cifras."
        ),
        name="fundamentals_worker",
    )

    technical_worker = create_agent(
        model=llm,
        tools=tools,
        system_prompt=(
            "Sos un analista técnico especializado en precio y tendencia de "
            "acciones. Usá get_stock_quote para la cotización actual, "
            "get_stock_price_history para el histórico de cierres, y "
            "calculate_sma para medias móviles y señales de tendencia. "
            "Respondé solo con lo que encontraste — no inventes cifras ni "
            "dés recomendaciones de compra/venta."
        ),
        name="technical_worker",
    )

    filings_worker = create_agent(
        model=llm,
        tools=tools,
        system_prompt=(
            "Sos un analista especializado en filings regulatorios de SEC "
            "EDGAR (10-K anual, 10-Q trimestral). Usá search_sec_filings para "
            "encontrar filings recientes y get_sec_company_facts para extraer "
            "datos financieros estructurados de esos filings. Respondé solo "
            "con lo que encontraste — no inventes cifras."
        ),
        name="filings_worker",
    )

    return {
        "fundamentals_worker": fundamentals_worker,
        "technical_worker": technical_worker,
        "filings_worker": filings_worker,
    }

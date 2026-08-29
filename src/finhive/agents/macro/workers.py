"""Workers ReAct del dominio Macro: tasas, inflación, indicadores.

Los 3 comparten el mismo set de tools de FRED (registradas en Unity Catalog,
ver infra/databricks/register_uc_functions.py) y se diferencian por prompt de
especialización — mismo patrón ReAct que el notebook de referencia del
bootcamp, con `langchain.agents.create_agent` (sucesor de
`langgraph.prebuilt.create_react_agent`, deprecado en LangGraph v1.0).
"""

from __future__ import annotations

from langchain.agents import create_agent
from langchain_core.tools import tool

from finhive.config.settings import get_chat_model
from finhive.tools.macro_data import (
    get_fred_series_history,
    get_fred_series_latest,
    search_fred_series,
)


def _macro_tools() -> list:
    """Envuelve las funciones de FRED como LangChain tools.

    Las mismas funciones ya están registradas en Unity Catalog
    (`infra/databricks/register_uc_functions.py`) para gobernanza/catálogo —
    ese es el valor "estilo MCP" que buscábamos (ver ADR 0004). Para la
    *ejecución* en sí se evita `UCFunctionToolkit`: su modo `local` genera un
    subproceso que hace `import resource` (módulo Unix-only), lo que lo rompe
    en Windows y hace que el LLM alucine ante el fallo silencioso. Llamar la
    función Python directamente acá es igual de válido — UC sigue siendo la
    fuente de verdad del contrato/schema de la tool — y evita esa dependencia
    frágil además de la latencia/cuota de cómputo serverless.
    """
    return [
        tool(search_fred_series),
        tool(get_fred_series_latest),
        tool(get_fred_series_history),
    ]


def build_macro_workers() -> dict:
    """Construye los 3 workers ReAct del dominio Macro.

    Returns:
        dict con los agentes compilados, con clave = nombre del worker.
    """
    tools = _macro_tools()
    llm = get_chat_model("worker")

    rates_worker = create_agent(
        model=llm,
        tools=tools,
        system_prompt=(
            "Sos un analista especializado en tasas de interés y política del "
            "banco central (Reserva Federal). Usá las tools de FRED disponibles "
            "para responder con datos reales y actualizados. Series relevantes: "
            "FEDFUNDS (Fed Funds Rate), DFF (Fed Funds Effective Rate). "
            "Si no conocés el series_id exacto, usá search_fred_series primero. "
            "Respondé solo con lo que encontraste — no inventes cifras."
        ),
        name="rates_worker",
    )

    inflation_worker = create_agent(
        model=llm,
        tools=tools,
        system_prompt=(
            "Sos un analista especializado en inflación y precios al consumidor. "
            "Usá las tools de FRED disponibles para responder con datos reales y "
            "actualizados. Series relevantes: CPIAUCSL (CPI), CPILFESL (core CPI), "
            "PCEPI (PCE Price Index). Si no conocés el series_id exacto, usá "
            "search_fred_series primero. Respondé solo con lo que encontraste — "
            "no inventes cifras."
        ),
        name="inflation_worker",
    )

    indicators_worker = create_agent(
        model=llm,
        tools=tools,
        system_prompt=(
            "Sos un analista especializado en indicadores macroeconómicos "
            "generales: crecimiento (GDP), empleo (UNRATE) y actividad económica. "
            "Usá las tools de FRED disponibles para responder con datos reales y "
            "actualizados. Si no conocés el series_id exacto, usá "
            "search_fred_series primero. Respondé solo con lo que encontraste — "
            "no inventes cifras."
        ),
        name="indicators_worker",
    )

    return {
        "rates_worker": rates_worker,
        "inflation_worker": inflation_worker,
        "indicators_worker": indicators_worker,
    }

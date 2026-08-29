"""Workers ReAct del dominio Crypto & Alt: mercado cripto y datos alternativos.

Mismo patrón que `finhive.agents.macro.workers`. Solo 2 workers (no 3 como
los demás dominios): market_data_worker y alt_data_worker, matching el
diseño original de ADR 0001.
"""

from __future__ import annotations

from langchain.agents import create_agent
from langchain_core.tools import tool

from finhive.config.settings import get_chat_model
from finhive.tools.crypto_data import (
    get_crypto_price,
    get_crypto_price_history,
    get_top_crypto_by_market_cap,
    get_trending_crypto,
    search_crypto_id,
)
from finhive.tools.wrappers import safe_tool


def _crypto_tools() -> list:
    return [
        tool(safe_tool(search_crypto_id)),
        tool(safe_tool(get_crypto_price)),
        tool(safe_tool(get_crypto_price_history)),
        tool(safe_tool(get_trending_crypto)),
        tool(safe_tool(get_top_crypto_by_market_cap)),
    ]


def build_crypto_alt_workers() -> dict:
    """Construye los 2 workers ReAct del dominio Crypto & Alt.

    Returns:
        dict con los agentes compilados, con clave = nombre del worker.
    """
    tools = _crypto_tools()
    llm = get_chat_model("worker")

    market_data_worker = create_agent(
        model=llm,
        tools=tools,
        system_prompt=(
            "Sos un analista especializado en precios y mercado de "
            "criptomonedas. Usá search_crypto_id primero si no sabés el id "
            "exacto de CoinGecko (ej. 'bitcoin' para BTC), después "
            "get_crypto_price o get_crypto_price_history. Respondé solo con "
            "lo que encontraste — no inventes cifras ni des recomendaciones "
            "de compra/venta."
        ),
        name="market_data_worker",
    )

    alt_data_worker = create_agent(
        model=llm,
        tools=tools,
        system_prompt=(
            "Sos un analista especializado en datos alternativos de "
            "criptomonedas: qué está en tendencia y el ranking por market "
            "cap. Usá get_trending_crypto y get_top_crypto_by_market_cap. "
            "Respondé solo con lo que encontraste — no inventes datos."
        ),
        name="alt_data_worker",
    )

    return {
        "market_data_worker": market_data_worker,
        "alt_data_worker": alt_data_worker,
    }

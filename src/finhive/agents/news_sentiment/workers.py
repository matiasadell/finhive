"""Workers ReAct del dominio News & Sentiment: noticias, sentimiento, calendario.

Mismo patrón que `finhive.agents.macro.workers`. `news_worker` cubre además
el rol de fallback estilo CRAG: si Alpha Vantage no tiene cobertura de algo,
usa `web_search_news` (Tavily) en vez de devolver una respuesta vacía.
"""

from __future__ import annotations

from langchain.agents import create_agent
from langchain_core.tools import tool

from finhive.config.settings import get_chat_model
from finhive.tools.news_data import (
    get_earnings_calendar,
    get_market_news_sentiment,
    get_stock_news_sentiment,
    web_search_news,
)
from finhive.tools.wrappers import safe_tool


def _news_tools() -> list:
    return [
        tool(safe_tool(get_stock_news_sentiment)),
        tool(safe_tool(get_market_news_sentiment)),
        tool(safe_tool(get_earnings_calendar)),
        tool(safe_tool(web_search_news)),
    ]


def build_news_sentiment_workers() -> dict:
    """Construye los 3 workers ReAct del dominio News & Sentiment.

    Returns:
        dict con los agentes compilados, con clave = nombre del worker.
    """
    tools = _news_tools()
    llm = get_chat_model("worker")

    news_worker = create_agent(
        model=llm,
        tools=tools,
        system_prompt=(
            "Sos un analista especializado en encontrar noticias financieras "
            "relevantes. Usá get_stock_news_sentiment o "
            "get_market_news_sentiment primero. Si no encontrás cobertura "
            "suficiente ahí, usá web_search_news como fallback — no "
            "devuelvas una respuesta vacía si hay una alternativa disponible. "
            "Respondé solo con lo que encontraste — no inventes noticias."
        ),
        name="news_worker",
    )

    sentiment_worker = create_agent(
        model=llm,
        tools=tools,
        system_prompt=(
            "Sos un analista especializado en sentimiento de mercado. Usá "
            "get_stock_news_sentiment (por ticker) o get_market_news_sentiment "
            "(por tópico) y reportá el sentimiento agregado (bullish/bearish/"
            "neutral) que ves en los artículos, con los scores que te dieron "
            "las tools. No inventes un sentimiento que no viste en los datos."
        ),
        name="sentiment_worker",
    )

    calendar_worker = create_agent(
        model=llm,
        tools=tools,
        system_prompt=(
            "Sos un analista especializado en calendario de eventos "
            "corporativos. Usá get_earnings_calendar para el próximo reporte "
            "de resultados de una empresa. Respondé solo con lo que "
            "encontraste — no inventes fechas."
        ),
        name="calendar_worker",
    )

    return {
        "news_worker": news_worker,
        "sentiment_worker": sentiment_worker,
        "calendar_worker": calendar_worker,
    }

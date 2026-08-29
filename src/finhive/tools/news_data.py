"""Tools de noticias y sentimiento: Alpha Vantage (sentiment estructurado,
calendario de earnings) y Tavily (búsqueda web general, fallback tipo CRAG
cuando Alpha Vantage no cubre algo).

Mismas reglas que el resto: funciones planas, type hints, docstrings
Google-style completos, sin parámetros con valor default.

Ojo con la cuota: el free tier de Alpha Vantage es chico (históricamente
~25 requests/día) — no llamar estas tools en loops de testing.
"""

from __future__ import annotations

import csv
import io

import requests

from finhive.config.settings import get_alpha_vantage_api_key, get_tavily_api_key

_ALPHA_VANTAGE_URL = "https://www.alphavantage.co/query"
_TAVILY_URL = "https://api.tavily.com/search"


def get_stock_news_sentiment(ticker: str, limit: int) -> str:
    """Devuelve noticias recientes de una acción con análisis de sentimiento.

    Usa el endpoint NEWS_SENTIMENT de Alpha Vantage: cada artículo viene con
    un sentiment score específico para el ticker pedido, no solo un
    sentiment genérico del artículo.

    Args:
        ticker: símbolo bursátil (ej. "AAPL").
        limit: cantidad máxima de artículos a devolver (recomendado: 5).

    Returns:
        Texto con título, sentimiento (label + score específico del ticker)
        y fecha de cada artículo.
    """
    response = requests.get(
        _ALPHA_VANTAGE_URL,
        params={
            "function": "NEWS_SENTIMENT",
            "tickers": ticker,
            "apikey": get_alpha_vantage_api_key(),
        },
        timeout=20,
    )
    response.raise_for_status()
    feed = response.json().get("feed", [])
    if not feed:
        return f"No se encontraron noticias recientes para '{ticker}'."
    lines = []
    for item in feed[:limit]:
        ticker_scores = {
            t["ticker"]: t for t in item.get("ticker_sentiment", []) if t["ticker"] == ticker
        }
        score = ticker_scores.get(ticker, {})
        lines.append(
            f"[{item.get('time_published', '')[:8]}] {item.get('title', '')} — "
            f"sentimiento para {ticker}: "
            f"{score.get('ticker_sentiment_label', 'N/A')} "
            f"({score.get('ticker_sentiment_score', 'N/A')})"
        )
    return f"Noticias recientes de {ticker} con sentimiento:\n" + "\n".join(lines)


def get_market_news_sentiment(topics: str, limit: int) -> str:
    """Devuelve noticias recientes de mercado sobre uno o más tópicos, con sentimiento.

    Args:
        topics: tópicos separados por coma, valores válidos de Alpha Vantage
            (ej. "technology", "earnings", "economy_macro",
            "financial_markets", "mergers_and_acquisitions").
        limit: cantidad máxima de artículos a devolver (recomendado: 5).

    Returns:
        Texto con título, sentimiento general y fecha de cada artículo.
    """
    response = requests.get(
        _ALPHA_VANTAGE_URL,
        params={
            "function": "NEWS_SENTIMENT",
            "topics": topics,
            "apikey": get_alpha_vantage_api_key(),
        },
        timeout=20,
    )
    response.raise_for_status()
    feed = response.json().get("feed", [])
    if not feed:
        return f"No se encontraron noticias recientes para el tópico '{topics}'."
    lines = [
        f"[{item.get('time_published', '')[:8]}] {item.get('title', '')} — "
        f"sentimiento general: {item.get('overall_sentiment_label', 'N/A')} "
        f"({item.get('overall_sentiment_score', 'N/A')})"
        for item in feed[:limit]
    ]
    return f"Noticias recientes sobre '{topics}':\n" + "\n".join(lines)


def get_earnings_calendar(ticker: str) -> str:
    """Devuelve el próximo reporte de earnings estimado de una empresa.

    Args:
        ticker: símbolo bursátil (ej. "AAPL").

    Returns:
        Texto con la fecha estimada del próximo earnings report y el EPS
        estimado, si Alpha Vantage tiene esa información.
    """
    response = requests.get(
        _ALPHA_VANTAGE_URL,
        params={
            "function": "EARNINGS_CALENDAR",
            "symbol": ticker,
            "horizon": "3month",
            "apikey": get_alpha_vantage_api_key(),
        },
        timeout=20,
    )
    response.raise_for_status()
    rows = list(csv.DictReader(io.StringIO(response.text)))
    if not rows:
        return f"No hay earnings próximos reportados para '{ticker}' en los próximos 3 meses."
    next_earnings = rows[0]
    return (
        f"Próximo earnings de {ticker}: {next_earnings.get('reportDate')} "
        f"(fin de período fiscal {next_earnings.get('fiscalDateEnding')}), "
        f"EPS estimado {next_earnings.get('estimate')} "
        f"{next_earnings.get('currency', 'USD')}."
    )


def web_search_news(query: str, max_results: int) -> str:
    """Busca noticias en la web abierta (fallback cuando Alpha Vantage no alcanza).

    Args:
        query: consulta de búsqueda en lenguaje natural (ej. "Apple earnings
            Q4 2026 reaction").
        max_results: cantidad máxima de resultados a devolver (recomendado: 5).

    Returns:
        Texto con título, URL y resumen de cada resultado.
    """
    response = requests.post(
        _TAVILY_URL,
        json={
            "api_key": get_tavily_api_key(),
            "query": query,
            "max_results": max_results,
            "search_depth": "basic",
        },
        timeout=20,
    )
    response.raise_for_status()
    results = response.json().get("results", [])
    if not results:
        return f"No se encontraron resultados web para '{query}'."
    lines = [
        f"{r.get('title', '')} ({r.get('url', '')}): {r.get('content', '')[:200]}"
        for r in results
    ]
    return f"Resultados de búsqueda web para '{query}':\n" + "\n\n".join(lines)

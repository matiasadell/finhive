"""Tools de mercado cripto y datos alternativos: CoinGecko (API pública, sin key).

Mismas reglas que el resto: funciones planas, type hints, docstrings
Google-style completos, sin parámetros con valor default.
"""

from __future__ import annotations

from datetime import UTC, datetime

import requests

_COINGECKO_BASE_URL = "https://api.coingecko.com/api/v3"


def search_crypto_id(query: str) -> str:
    """Busca el id interno de CoinGecko para una cripto por nombre o símbolo.

    Necesario antes de llamar a get_crypto_price/get_crypto_price_history:
    esas tools esperan el id de CoinGecko (ej. "bitcoin"), no el símbolo
    (ej. "BTC").

    Args:
        query: nombre o símbolo de la cripto (ej. "bitcoin", "BTC", "ethereum").

    Returns:
        Texto con hasta 5 coincidencias: id, nombre y símbolo.
    """
    response = requests.get(
        f"{_COINGECKO_BASE_URL}/search", params={"query": query}, timeout=15
    )
    response.raise_for_status()
    coins = response.json().get("coins", [])[:5]
    if not coins:
        return f"No se encontraron criptomonedas para '{query}'."
    lines = [f"{c['id']}: {c['name']} ({c['symbol']})" for c in coins]
    return f"Resultados de búsqueda para '{query}':\n" + "\n".join(lines)


def get_crypto_price(coin_id: str) -> str:
    """Devuelve el precio actual de una criptomoneda y su variación en 24h.

    Args:
        coin_id: id de CoinGecko (ej. "bitcoin", "ethereum"). Si no se conoce,
            usar primero search_crypto_id.

    Returns:
        Texto con precio actual en USD, variación 24h y market cap.
    """
    response = requests.get(
        f"{_COINGECKO_BASE_URL}/coins/{coin_id}",
        params={
            "localization": "false",
            "tickers": "false",
            "community_data": "false",
            "developer_data": "false",
        },
        timeout=15,
    )
    response.raise_for_status()
    market = response.json().get("market_data", {})
    price = market.get("current_price", {}).get("usd")
    change_24h = market.get("price_change_percentage_24h")
    market_cap = market.get("market_cap", {}).get("usd")
    return (
        f"{coin_id}: precio actual ${price} USD, variación 24h "
        f"{change_24h:.2f}%, market cap ${market_cap} USD."
    )


def get_crypto_price_history(coin_id: str, days: int) -> str:
    """Devuelve el historial de precios diarios de una criptomoneda.

    Args:
        coin_id: id de CoinGecko (ej. "bitcoin"). Si no se conoce, usar
            primero search_crypto_id.
        days: cantidad de días de historial (ej. 7, 30, 90).

    Returns:
        Texto con un precio de cierre aproximado por día.
    """
    response = requests.get(
        f"{_COINGECKO_BASE_URL}/coins/{coin_id}/market_chart",
        params={"vs_currency": "usd", "days": days},
        timeout=15,
    )
    response.raise_for_status()
    prices = response.json().get("prices", [])
    if not prices:
        return f"No hay historial de precios disponible para '{coin_id}'."
    daily: dict[str, float] = {}
    for timestamp_ms, price in prices:
        day = datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC).date().isoformat()
        daily[day] = price  # se queda con el último precio observado de cada día
    lines = [f"{day}: ${price:.2f}" for day, price in daily.items()]
    return f"Historial de precio de {coin_id} (últimos {days} días):\n" + "\n".join(lines)


def get_trending_crypto() -> str:
    """Devuelve las criptomonedas en tendencia (más buscadas) en CoinGecko ahora mismo.

    Returns:
        Texto con nombre y símbolo de las criptos en tendencia.
    """
    response = requests.get(f"{_COINGECKO_BASE_URL}/search/trending", timeout=15)
    response.raise_for_status()
    coins = response.json().get("coins", [])
    if not coins:
        return "No hay datos de tendencias disponibles en este momento."
    lines = [f"{c['item']['name']} ({c['item']['symbol']})" for c in coins]
    return "Criptomonedas en tendencia ahora mismo:\n" + "\n".join(lines)


def get_top_crypto_by_market_cap(limit: int) -> str:
    """Devuelve las criptomonedas top por market cap.

    Args:
        limit: cantidad de criptomonedas a devolver (recomendado: 10).

    Returns:
        Texto con id, precio y market cap de cada una, de mayor a menor cap.
    """
    response = requests.get(
        f"{_COINGECKO_BASE_URL}/coins/markets",
        params={
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": limit,
            "page": 1,
        },
        timeout=15,
    )
    response.raise_for_status()
    coins = response.json()
    if not coins:
        return "No se pudo obtener el ranking de criptomonedas por market cap."
    lines = [
        f"{c['id']}: ${c['current_price']} USD, market cap ${c['market_cap']} USD"
        for c in coins
    ]
    return f"Top {limit} criptomonedas por market cap:\n" + "\n".join(lines)

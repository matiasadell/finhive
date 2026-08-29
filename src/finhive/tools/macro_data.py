"""Tools de datos macroeconómicos (FRED — Federal Reserve Economic Data).

Funciones planas, con type hints y docstrings Google-style completos: son la
fuente de verdad tanto para el uso directo como para el registro en Unity
Catalog (`unitycatalog-ai` parsea el docstring para la descripción de la tool
y de cada parámetro — ver infra/databricks/register_uc_functions.py).
"""

from __future__ import annotations

import requests

from finhive.config.settings import get_fred_api_key

_FRED_BASE_URL = "https://api.stlouisfed.org/fred"


def search_fred_series(search_text: str, limit: int) -> str:
    """Busca series económicas de FRED por texto libre.

    Útil para descubrir el `series_id` correcto antes de llamar a
    `get_fred_series_latest` o `get_fred_series_history` — por ejemplo,
    buscar "federal funds rate" para encontrar el id `FEDFUNDS`.

    Nota: Unity Catalog Functions no admite parámetros con valor default,
    por eso `limit` es obligatorio acá (usar 5 si no hay una razón para
    pedir más o menos resultados).

    Args:
        search_text: texto de búsqueda en lenguaje natural (ej. "inflation cpi",
            "unemployment rate", "federal funds rate").
        limit: cantidad máxima de resultados a devolver (recomendado: 5).

    Returns:
        Texto con una línea por serie encontrada: "{series_id}: {title}".
    """
    response = requests.get(
        f"{_FRED_BASE_URL}/series/search",
        params={
            "search_text": search_text,
            "api_key": get_fred_api_key(),
            "file_type": "json",
            "limit": limit,
        },
        timeout=15,
    )
    response.raise_for_status()
    series = response.json().get("seriess", [])
    if not series:
        return f"No se encontraron series de FRED para '{search_text}'."
    return "\n".join(f"{s['id']}: {s['title']}" for s in series)


def get_fred_series_latest(series_id: str) -> str:
    """Devuelve el último valor observado de una serie de FRED.

    Args:
        series_id: identificador de la serie en FRED (ej. "FEDFUNDS", "CPIAUCSL",
            "UNRATE", "GDP"). Si no se sabe el id exacto, usar primero
            `search_fred_series`.

    Returns:
        Texto con el valor y la fecha de la observación más reciente.
    """
    response = requests.get(
        f"{_FRED_BASE_URL}/series/observations",
        params={
            "series_id": series_id,
            "api_key": get_fred_api_key(),
            "file_type": "json",
            "sort_order": "desc",
            "limit": 1,
        },
        timeout=15,
    )
    response.raise_for_status()
    observations = response.json().get("observations", [])
    if not observations:
        return f"No hay observaciones disponibles para la serie '{series_id}'."
    obs = observations[0]
    return f"Serie {series_id}: valor {obs['value']} al {obs['date']}."


def get_fred_series_history(series_id: str, limit: int) -> str:
    """Devuelve las últimas N observaciones de una serie de FRED.

    Nota: Unity Catalog Functions no admite parámetros con valor default,
    por eso `limit` es obligatorio acá (usar 12 si no hay una razón para
    pedir más o menos observaciones).

    Args:
        series_id: identificador de la serie en FRED (ej. "CPIAUCSL").
        limit: cantidad de observaciones recientes a devolver (recomendado: 12).

    Returns:
        Texto con una línea "{fecha}: {valor}" por observación, de más
        reciente a más antigua.
    """
    response = requests.get(
        f"{_FRED_BASE_URL}/series/observations",
        params={
            "series_id": series_id,
            "api_key": get_fred_api_key(),
            "file_type": "json",
            "sort_order": "desc",
            "limit": limit,
        },
        timeout=15,
    )
    response.raise_for_status()
    observations = response.json().get("observations", [])
    if not observations:
        return f"No hay observaciones disponibles para la serie '{series_id}'."
    lines = [f"{obs['date']}: {obs['value']}" for obs in observations]
    return f"Últimas {len(lines)} observaciones de {series_id}:\n" + "\n".join(lines)

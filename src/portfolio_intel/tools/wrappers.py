"""Wrapper defensivo para tools: convierte excepciones en observaciones.

Patrón heredado de finhive (`tools/wrappers.py`, hallazgo real ahí probando
crypto_alt contra CoinGecko bajo rate limiting): sin este wrapper, una
excepción dentro de una tool (dato faltante, backend Databricks
inalcanzable, un cálculo que no puede correr con los datos que llegaron) se
propaga sin capturar y crashea el `graph.invoke()` completo -- no queda como
una observación que el agente ReAct pueda ver y manejar, simplemente revienta
la request entera. Aplicable a las 4 tools deterministas de este proyecto por
igual (`tools/prioritization_tools.py`, `duplication_tools.py`,
`value_realization_tools.py`, `recommendation_tools.py`).

Uso: `tool(safe_tool(mi_funcion))` en vez de `tool(mi_funcion)` al construir
la lista de tools de cada worker.
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import TypeVar

F = TypeVar("F", bound=Callable[..., str])


def safe_tool(func: F) -> F:
    """Envuelve una función de tool para que las excepciones se devuelvan
    como texto de error en vez de propagarse y crashear el grafo.

    El texto de error queda como observación del ReAct loop: el LLM lo ve y
    puede decidir reintentar con otro input, usar otra tool, o admitirle al
    usuario que esa fuente de datos no está disponible en este momento — en
    vez de que la excepción tire abajo toda la invocación del grafo.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:  # noqa: BLE001 - a propósito: cualquier excepción de la tool
            return (
                f"Error al ejecutar {func.__name__}: {e}. "
                "Esta fuente de datos no está disponible en este momento — "
                "probá con otra tool o con otros parámetros, o si no hay "
                "alternativa, decile al usuario que no se pudo obtener este "
                "dato ahora en vez de inventarlo."
            )

    return wrapper  # type: ignore[return-value]

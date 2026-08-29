"""Wrapper defensivo para tools: convierte excepciones en observaciones.

Hallazgo real (probando crypto_alt contra CoinGecko bajo rate limiting):
sin este wrapper, una excepción dentro de una tool (error de red, rate limit
429, timeout) se propaga sin capturar y crashea el `graph.invoke()` completo
del sistema jerárquico — no queda como una observación que el ReAct worker
pueda ver y manejar, simplemente revienta la request del usuario entera.
Aplicable a los 5 dominios por igual, no es específico de ninguna API.

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

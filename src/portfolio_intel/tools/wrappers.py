from __future__ import annotations

import functools
from collections.abc import Callable
from typing import TypeVar

F = TypeVar("F", bound=Callable[..., str])


def safe_tool(func: F) -> F:
    # Sin esto, una excepción dentro de una tool crashea graph.invoke()
    # entero en vez de quedar como observación que el agente ReAct pueda manejar.
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:  # noqa: BLE001
            return (
                f"Error al ejecutar {func.__name__}: {e}. "
                "Esta fuente de datos no está disponible en este momento — "
                "probá con otra tool o con otros parámetros, o si no hay "
                "alternativa, decile al usuario que no se pudo obtener este "
                "dato ahora en vez de inventarlo."
            )

    return wrapper  # type: ignore[return-value]

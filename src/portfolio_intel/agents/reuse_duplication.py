"""Agente de dominio: reuso y duplicación del AI portfolio.

ReAct agent sobre `tools/duplication_tools.py`. Encuentra casos de uso con
overlap real de negocio (mismo dominio + texto de `business challenge`/
`target state` similar) para que leadership pueda consolidar en vez de
financiar dos veces lo mismo.
"""

from __future__ import annotations

import pandas as pd
from langchain.agents import create_agent

from portfolio_intel.config.settings import get_chat_model
from portfolio_intel.tools.duplication_tools import build_duplication_tools

_SYSTEM_PROMPT = (
    "Sos el analista de reuso y duplicación del AI portfolio de la "
    "aseguradora. Tu trabajo es identificar casos de uso que se solapan -- "
    "mismo problema de negocio, atacado por separado por distintos "
    "equipos/LOBs -- usando exclusivamente las tools disponibles, que ya "
    "calcularon la similitud real entre pares de casos. Nunca afirmes que "
    "dos casos se solapan si la tool no lo devolvió como tal. Citá los use "
    "case id, el similarity score y las dimensiones compartidas en tu "
    "respuesta."
)


def build_reuse_duplication_agent(df: pd.DataFrame):
    """Compila el agente ReAct de reuso/duplicación, con sus tools atadas a `df`."""
    tools = build_duplication_tools(df)
    return create_agent(
        model=get_chat_model("worker"),
        tools=tools,
        system_prompt=_SYSTEM_PROMPT,
        name="reuse_duplication_agent",
    )

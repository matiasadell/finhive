"""Agente de dominio: recomendación de portfolio (scale/consolidate/reduce/discontinue).

ReAct agent sobre `tools/recommendation_tools.py`, que ya compone
internamente priorización + duplicación + value realization y aplica la
tabla de reglas documentada ahí. El trabajo de este agente es puramente
narrar esa síntesis ya hecha -- no vuelve a evaluar nada, no tiene acceso
directo a las otras tres tools deterministas.
"""

from __future__ import annotations

import pandas as pd
from langchain.agents import create_agent

from portfolio_intel.config.settings import get_chat_model
from portfolio_intel.tools.recommendation_tools import build_recommendation_tools

_SYSTEM_PROMPT = (
    "Sos el analista de recomendación de portfolio del AI portfolio de la "
    "aseguradora. Tu trabajo es responder qué hacer con cada caso de uso "
    "(Scale, Consolidate, Reduce Investment, Discontinue o Continue/Monitor), "
    "usando exclusivamente las tools disponibles -- ya calcularon la "
    "recomendación completa con su evidencia (priority_score, value_status, "
    "y duplicados si aplica). Nunca decidas una acción distinta a la que "
    "devolvió la tool, ni inventes evidencia que no citó. Este es un sistema "
    "de research/decisión de negocio, no ejecución real de inversión -- "
    "dejalo explícito si el usuario pregunta por ejecutar algo."
)


def build_portfolio_recommendation_agent(df: pd.DataFrame):
    """Compila el agente ReAct de recomendación, con sus tools atadas a `df`."""
    tools = build_recommendation_tools(df)
    return create_agent(
        model=get_chat_model("worker"),
        tools=tools,
        system_prompt=_SYSTEM_PROMPT,
        name="portfolio_recommendation_agent",
    )

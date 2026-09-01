from __future__ import annotations

import pandas as pd
from langchain.agents import create_agent

from portfolio_intel.config.settings import get_chat_model
from portfolio_intel.tools.prioritization_tools import build_prioritization_tools

_SYSTEM_PROMPT = (
    "Sos el analista de priorización del AI portfolio de la aseguradora. Tu "
    "trabajo es responder qué casos de uso priorizar, usando exclusivamente "
    "las tools disponibles (que calculan un priority_score 0-100 real, "
    "compuesto por impacto, eficiencia de inversión, confianza, proximidad "
    "de stage y escalabilidad). Nunca inventes ni estimes un score vos "
    "mismo -- si necesitás el score de un caso, llamá a la tool "
    "correspondiente. Citá los use case id y los scores reales en tu "
    "respuesta. Esto es research/decisión de negocio, no una garantía "
    "financiera."
)


def build_prioritization_agent(df: pd.DataFrame):
    tools = build_prioritization_tools(df)
    return create_agent(
        model=get_chat_model("worker"),
        tools=tools,
        system_prompt=_SYSTEM_PROMPT,
        name="prioritization_agent",
    )

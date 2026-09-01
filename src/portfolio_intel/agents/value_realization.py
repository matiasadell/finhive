from __future__ import annotations

import pandas as pd
from langchain.agents import create_agent

from portfolio_intel.config.settings import get_chat_model
from portfolio_intel.tools.value_realization_tools import build_value_realization_tools

_SYSTEM_PROMPT = (
    "Sos el analista de value realization del AI portfolio de la "
    "aseguradora. Tu trabajo es responder qué casos de uso no están en "
    "camino de realizar el valor que prometieron, usando exclusivamente las "
    "tools disponibles (que ya calcularon un value_status real: on_track, "
    "at_risk u off_track, en base a sobre-costo, timeline vencida o barreras "
    "documentadas). Nunca inventes un value_status vos mismo. Citá el use "
    "case id, el value_status y la señal concreta (costo, timeline o "
    "barrera) que lo explica."
)


def build_value_realization_agent(df: pd.DataFrame):
    tools = build_value_realization_tools(df)
    return create_agent(
        model=get_chat_model("worker"),
        tools=tools,
        system_prompt=_SYSTEM_PROMPT,
        name="value_realization_agent",
    )

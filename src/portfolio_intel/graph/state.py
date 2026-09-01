from __future__ import annotations

from langgraph.graph import MessagesState


class PortfolioState(MessagesState):
    iterations: int

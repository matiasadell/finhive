# Patrón "models from code": mlflow.pyfunc.log_model(python_model="chat_agent.py")
# importa y ejecuta este módulo directo -- ver infra/databricks/deploy_agent.py.

from __future__ import annotations

import uuid

from mlflow.models import set_model
from mlflow.pyfunc import ResponsesAgent
from mlflow.types.responses import ResponsesAgentRequest, ResponsesAgentResponse

_graph = None


def _get_graph():
    global _graph
    if _graph is None:
        from portfolio_intel.data.store import load_portfolio_data
        from portfolio_intel.graph import build_top_supervisor

        df = load_portfolio_data().get_use_cases()
        _graph = build_top_supervisor(df)
    return _graph


def _extract_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            part.get("text", "") for part in content if isinstance(part, dict) and "text" in part
        )
    return str(content)


class PortfolioIntelAgent(ResponsesAgent):
    def predict(self, request: ResponsesAgentRequest) -> ResponsesAgentResponse:
        graph = _get_graph()
        messages = [(m.role, _extract_text(m.content)) for m in request.input]

        result = graph.invoke({"messages": messages})
        answer = str(result["messages"][-1].content)

        return ResponsesAgentResponse(
            output=[self.create_text_output_item(text=answer, id=str(uuid.uuid4()))]
        )


set_model(PortfolioIntelAgent())

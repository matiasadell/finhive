"""Envuelve `build_top_supervisor()` con la interfaz `ResponsesAgent` de MLflow.

Patrón "models from code" (`mlflow.models.set_model(...)` al final del archivo):
`mlflow.pyfunc.log_model(python_model="chat_agent.py", ...)` importa y ejecuta
este módulo directamente en vez de intentar serializar el objeto Python del
grafo compilado -- necesario porque loguear un `CompiledStateGraph` de
LangGraph directo con el flavor `langchain` de MLflow es un bug conocido (no
soporta esa clase). `ResponsesAgent` (no `ChatAgent`) porque es lo que
Databricks recomienda hoy para wrappear agentes de terceros -- ver ADR 0015.

No reimplementa nada del grafo: guardrails, memoria (ADR 0012) y routing entre
los 5 dominios siguen siendo exactamente los mismos que usan el notebook de
demo y `run_eval.py`, invocando `build_top_supervisor()` tal cual.
"""

from __future__ import annotations

import uuid

from mlflow.models import set_model
from mlflow.pyfunc import ResponsesAgent
from mlflow.types.responses import ResponsesAgentRequest, ResponsesAgentResponse

_graph = None


def _get_graph():
    global _graph
    if _graph is None:
        from finhive.graph import build_top_supervisor

        _graph = build_top_supervisor()
    return _graph


def _extract_text(content) -> str:
    """Normaliza el contenido de un mensaje de `ResponsesAgentRequest.input`.

    Puede venir como string plano o como lista de content parts (formato
    Responses API) -- FinHive es texto puro, así que alcanza con concatenar
    las partes de tipo texto.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            part.get("text", "") for part in content if isinstance(part, dict) and "text" in part
        )
    return str(content)


class FinHiveAgent(ResponsesAgent):
    """Adaptador `ResponsesAgent` sobre el grafo jerárquico de FinHive."""

    def predict(self, request: ResponsesAgentRequest) -> ResponsesAgentResponse:
        graph = _get_graph()

        # `thread_id` opcional vía `custom_inputs` -- si el caller lo manda,
        # se aprovecha la memoria de sesión real (ADR 0012) entre llamadas al
        # endpoint; si no, cada invocación es independiente. Mismo patrón que
        # `run_eval.py` (siempre nuevo) y el notebook de demo (uno por sesión).
        custom_inputs = request.custom_inputs or {}
        thread_id = custom_inputs.get("thread_id") or f"agent-{uuid.uuid4()}"

        messages = [(m.role, _extract_text(m.content)) for m in request.input]

        result = graph.invoke(
            {"messages": messages},
            config={"configurable": {"thread_id": thread_id}},
        )
        answer = str(result["messages"][-1].content)

        return ResponsesAgentResponse(
            output=[self.create_text_output_item(text=answer, id=str(uuid.uuid4()))]
        )


set_model(FinHiveAgent())

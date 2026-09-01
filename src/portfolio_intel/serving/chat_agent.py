"""Envuelve `build_top_supervisor()` con la interfaz `ResponsesAgent` de MLflow.

Patrón "models from code" (`mlflow.models.set_model(...)` al final del archivo),
mismo que finhive (`docs/architecture/adr/finhive-legacy/`, ADR 0015):
`mlflow.pyfunc.log_model(python_model="chat_agent.py", ...)` importa y ejecuta
este módulo directo en vez de intentar serializar el objeto Python del grafo
compilado -- loguear un `CompiledStateGraph` de LangGraph directo con el
flavor `langchain` de MLflow es un bug conocido (no soporta esa clase).
`ResponsesAgent` (no `ChatAgent`) porque es lo que Databricks recomienda hoy
para wrappear agentes de terceros.

A diferencia de finhive, no hay `thread_id`/memoria de sesión acá -- este
proyecto no tiene memoria persistente (ver `prompts/non_goals.md`, ADR
0004): cada invocación del endpoint carga el portfolio actual desde el
backend configurado (`PORTFOLIO_INTEL_DATA_BACKEND` -- tiene que ser
`databricks` en el endpoint desplegado, ver `infra/databricks/deploy_agent.py`)
y responde fresco, sin arrastrar historial de invocaciones anteriores.
"""

from __future__ import annotations

import uuid

from mlflow.models import set_model
from mlflow.pyfunc import ResponsesAgent
from mlflow.types.responses import ResponsesAgentRequest, ResponsesAgentResponse

_graph = None


def _get_graph():
    """Compila el grafo una única vez por proceso del contenedor de serving.

    Carga el portfolio (`load_portfolio_data().get_use_cases()`) en el mismo
    momento -- un snapshot fijo por proceso, no por request. Igual que en
    `notebooks/00_demo.py`, esto asume que el portfolio no cambia dentro de
    la vida de un mismo proceso del endpoint; si eso deja de ser cierto (ej.
    el equipo empieza a actualizar el AI Use Case Inventory varias veces por
    día y espera que el endpoint lo refleje sin un restart), este cacheo
    global tiene que volver a evaluarse.
    """
    global _graph
    if _graph is None:
        from portfolio_intel.data.store import load_portfolio_data
        from portfolio_intel.graph import build_top_supervisor

        df = load_portfolio_data().get_use_cases()
        _graph = build_top_supervisor(df)
    return _graph


def _extract_text(content) -> str:
    """Normaliza el contenido de un mensaje de `ResponsesAgentRequest.input`.

    Puede venir como string plano o como lista de content parts (formato
    Responses API) -- Portfolio Intel es texto puro, así que alcanza con
    concatenar las partes de tipo texto.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            part.get("text", "") for part in content if isinstance(part, dict) and "text" in part
        )
    return str(content)


class PortfolioIntelAgent(ResponsesAgent):
    """Adaptador `ResponsesAgent` sobre el grafo jerárquico de Portfolio Intel."""

    def predict(self, request: ResponsesAgentRequest) -> ResponsesAgentResponse:
        graph = _get_graph()
        messages = [(m.role, _extract_text(m.content)) for m in request.input]

        result = graph.invoke({"messages": messages})
        answer = str(result["messages"][-1].content)

        return ResponsesAgentResponse(
            output=[self.create_text_output_item(text=answer, id=str(uuid.uuid4()))]
        )


set_model(PortfolioIntelAgent())

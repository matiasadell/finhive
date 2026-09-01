"""Scorers (row-level) para `mlflow.genai.evaluate()` — ver `run_eval.py` y ADR 0014.

Firma estándar de MLflow: `@scorer` sobre una función con argumentos
keyword-only entre `inputs` (lo que recibió `predict_fn`), `outputs` (lo que
devolvió `predict_fn` para ese ejemplo) y `expectations` (los valores
esperados del dataset dorado, ej. `expected_teams`). Migrado desde
`langsmith.evaluate()` (ADR 0013) sin cambiar la lógica de cada evaluador —
solo la firma: `run.outputs` -> `outputs`, `example.outputs` -> `expectations`,
`example.inputs` -> `inputs`.
"""

from __future__ import annotations

from typing import TypedDict

from mlflow.genai.scorers import scorer

from finhive.config.settings import get_chat_model

_GROUNDEDNESS_PROMPT = (
    "Sos un evaluador de groundedness para FinHive, un sistema de research "
    "financiero multiagente. Te paso una pregunta, la respuesta final que "
    "dio el sistema, y la evidencia real de los equipos de dominio que "
    "consultaron tools (FRED, yfinance, SEC EDGAR, Alpha Vantage, "
    "CoinGecko). Decidí si la respuesta está respaldada por esa evidencia — "
    "cifras, fechas y afirmaciones concretas consistentes con ella — o si "
    "contiene datos específicos sin respaldo visible (señal de "
    "alucinación). grounded='no' solo ante una afirmación concreta sin "
    "respaldo; una respuesta que admite no tener el dato cuenta como "
    "grounded='si'. Si la respuesta menciona nombres, rankings u otros "
    "datos que sí coinciden con la evidencia, aunque no repita cada cifra "
    "exacta, también cuenta como grounded='si' — falta de detalle no es lo "
    "mismo que alucinación."
)


class _GroundednessScore(TypedDict):
    grounded: str
    reason: str


@scorer
def routing_accuracy(*, outputs: dict, expectations: dict) -> float:
    """1.0 si el/los equipo(s) invocados coinciden con lo esperado, 0.0 si no.

    Para preguntas de un solo dominio: exacto. Para cross-domain (2+ equipos
    esperados): alcanza con que todos los esperados hayan sido tocados (no
    penaliza que además se sume un equipo extra). Para preguntas fuera de
    scope (`expected_teams=[]`): correcto si `input_guardrail` bloqueó el
    pedido sin invocar ningún equipo.
    """
    outputs = outputs or {}
    expected_teams = set((expectations or {}).get("expected_teams", []))
    actual_teams = set(outputs.get("actual_teams", []))
    blocked = bool(outputs.get("blocked", False))

    if not expected_teams:
        correct = blocked and not actual_teams
    else:
        correct = (not blocked) and expected_teams.issubset(actual_teams)

    return 1.0 if correct else 0.0


@scorer
def latency(*, outputs: dict) -> float:
    """Latencia de `graph.invoke()` en segundos, medida en `run_eval.predict_fn()`."""
    outputs = outputs or {}
    return outputs.get("latency_seconds", 0.0)


@scorer
def groundedness(*, inputs: dict, outputs: dict) -> float | None:
    """LLM-judge (modelo supervisor, no worker) sobre si la respuesta cita evidencia real.

    No aplica a preguntas bloqueadas por `input_guardrail` (no hay respuesta
    de dominio que evaluar) — devuelve `None` en ese caso, que
    `mlflow.genai.evaluate()` excluye del promedio en vez de contarlo como 0.

    Usa `"supervisor"` (Llama 3.3 70B), no `"worker"` (Llama 3.1 8B): en la
    primera corrida completa del dataset dorado, el modelo worker devolvía
    `grounded='no'` incluso ante una coincidencia literal palabra por
    palabra entre respuesta y evidencia, con una razón fabricada — no era
    un problema de prompt, el de 8B no es confiable para este juicio
    semántico. Mismo hallazgo aplicado retroactivamente a
    `output_guardrail_node` (ADR 0011) — ver ADR 0013. Se conserva este
    prompt/judge propio tal cual en la migración a MLflow (ADR 0014) en vez
    de adoptar el judge built-in `RetrievalGroundedness` — no hay necesidad
    de re-validar un judge nuevo cuando este ya está probado.
    """
    outputs = outputs or {}
    if outputs.get("blocked"):
        return None

    evidence = outputs.get("team_evidence", "")
    answer = outputs.get("answer", "")
    if not evidence:
        return None

    llm = get_chat_model("supervisor", temperature=0.0)
    structured_llm = llm.with_structured_output(_GroundednessScore)
    response = structured_llm.invoke(
        [
            {"role": "system", "content": _GROUNDEDNESS_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Pregunta: {(inputs or {}).get('question', '')}\n\n"
                    f"Respuesta final: {answer}\n\n"
                    f"Evidencia de los equipos:\n{evidence}"
                ),
            },
        ]
    )
    grounded = str(response.get("grounded", "si")).strip().lower() in ("si", "sí", "yes", "true")
    return 1.0 if grounded else 0.0

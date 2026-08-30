"""Evaluadores (row-level) para `langsmith.evaluate()` — ver `run_eval.py` y ADR 0013.

Firma estándar de LangSmith: `evaluator(run, example) -> dict`. `run.outputs`
es lo que devolvió `run_eval.target()` para ese ejemplo; `example.outputs`
son los valores esperados del dataset dorado (`expected_teams`).
"""

from __future__ import annotations

from typing import TypedDict

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


def routing_accuracy_evaluator(run, example) -> dict:
    """1.0 si el/los equipo(s) invocados coinciden con lo esperado, 0.0 si no.

    Para preguntas de un solo dominio: exacto. Para cross-domain (2+ equipos
    esperados): alcanza con que todos los esperados hayan sido tocados (no
    penaliza que además se sume un equipo extra). Para preguntas fuera de
    scope (`expected_teams=[]`): correcto si `input_guardrail` bloqueó el
    pedido sin invocar ningún equipo.
    """
    outputs = run.outputs or {}
    expected_teams = set((example.outputs or {}).get("expected_teams", []))
    actual_teams = set(outputs.get("actual_teams", []))
    blocked = bool(outputs.get("blocked", False))

    if not expected_teams:
        correct = blocked and not actual_teams
    else:
        correct = (not blocked) and expected_teams.issubset(actual_teams)

    return {"key": "routing_accuracy", "score": 1.0 if correct else 0.0}


def latency_evaluator(run, example) -> dict:
    """Latencia de `graph.invoke()` en segundos, medida en `run_eval.target()`."""
    outputs = run.outputs or {}
    return {"key": "latency_seconds", "score": outputs.get("latency_seconds", 0.0)}


def groundedness_evaluator(run, example) -> dict:
    """LLM-judge (modelo supervisor, no worker) sobre si la respuesta cita evidencia real.

    No aplica a preguntas bloqueadas por `input_guardrail` (no hay respuesta
    de dominio que evaluar) — devuelve `score=None` en ese caso, que
    LangSmith/`to_pandas()` excluyen del promedio en vez de contarlo como 0.

    Usa `"supervisor"` (Llama 3.3 70B), no `"worker"` (Llama 3.1 8B): en la
    primera corrida completa del dataset dorado, el modelo worker devolvía
    `grounded='no'` incluso ante una coincidencia literal palabra por
    palabra entre respuesta y evidencia, con una razón fabricada — no era
    un problema de prompt, el de 8B no es confiable para este juicio
    semántico. Mismo hallazgo aplicado retroactivamente a
    `output_guardrail_node` (ADR 0011) — ver ADR 0013.
    """
    outputs = run.outputs or {}
    if outputs.get("blocked"):
        return {"key": "groundedness", "score": None, "comment": "bloqueado por input_guardrail"}

    evidence = outputs.get("team_evidence", "")
    answer = outputs.get("answer", "")
    if not evidence:
        return {"key": "groundedness", "score": None, "comment": "sin evidencia de equipos"}

    llm = get_chat_model("supervisor", temperature=0.0)
    structured_llm = llm.with_structured_output(_GroundednessScore)
    response = structured_llm.invoke(
        [
            {"role": "system", "content": _GROUNDEDNESS_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Pregunta: {(example.inputs or {}).get('question', '')}\n\n"
                    f"Respuesta final: {answer}\n\n"
                    f"Evidencia de los equipos:\n{evidence}"
                ),
            },
        ]
    )
    grounded = str(response.get("grounded", "si")).strip().lower() in ("si", "sí", "yes", "true")
    return {
        "key": "groundedness",
        "score": 1.0 if grounded else 0.0,
        "comment": response.get("reason", ""),
    }

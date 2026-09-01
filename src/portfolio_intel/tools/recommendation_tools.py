"""Síntesis de recomendación determinista: scale / consolidate / reduce / discontinue.

Compone las tres tools anteriores (`prioritization_tools`,
`duplication_tools`, `value_realization_tools`) y aplica una tabla de reglas
explícita -- nunca le pide al LLM que "decida" la acción, solo que la narre.
Esta es la tool que respalda directamente el deliverable de "executive
recommendation output" del challenge (ver `reporting/executive_report.py`,
Task 11).

## Tabla de reglas (en orden de precedencia -- la primera que aplica gana)

1. **Consolidate** — el caso aparece en algún par de duplicados
   (`duplication_tools.duplicated_use_case_ids`), sea cual sea su propio
   `priority_score` o `value_status`. Construir/mantener dos veces lo mismo
   es un desperdicio de inversión incluso si ambas versiones andan bien
   individualmente -- la acción correcta es consolidar, no compararlas por
   score.
2. **Discontinue** — no está duplicado, `priority_score` bajo
   (`< _LOW_PRIORITY_THRESHOLD`), y además `value_status` en (`at_risk`,
   `off_track`) **o** el caso todavía está en un stage pre-inversión real
   (`Ideation`/`On Hold`). La segunda condición existe porque un caso recién
   levantado en Ideation, de baja prioridad, todavía no tuvo tiempo de
   "fallar" en value realization -- no hay timeline ni costo real corriendo
   todavía para que las señales de `value_realization_tools` disparen --
   pero es exactamente el tipo de caso que no vale la pena seguir
   madurando: baja prioridad y sin ninguna inversión real hundida todavía.
3. **Reduce Investment** — no está duplicado, `value_status` en (`at_risk`,
   `off_track`) pero `priority_score` no es bajo: vale la pena mantenerlo,
   pero no al ritmo de inversión actual hasta resolver el problema de valor.
4. **Scale** — no está duplicado, `priority_score` alto
   (`>= _HIGH_PRIORITY_THRESHOLD`) y `value_status` = `on_track`: candidato
   real a más inversión/rollout.
5. **Continue/Monitor** — todo lo que no cae en ninguna de las anteriores.
"""

from __future__ import annotations

import pandas as pd

from portfolio_intel.tools.duplication_tools import (
    duplicated_use_case_ids,
    get_use_case_overlap_detail,
)
from portfolio_intel.tools.prioritization_tools import compute_priority_scores
from portfolio_intel.tools.value_realization_tools import compute_value_realization_status
from portfolio_intel.tools.wrappers import safe_tool

_HIGH_PRIORITY_THRESHOLD = 65.0
_LOW_PRIORITY_THRESHOLD = 35.0

_VALUE_AT_RISK = {"at_risk", "off_track"}
_PRE_INVESTMENT_STAGES = {"Ideation", "On Hold"}


def generate_portfolio_recommendations(df: pd.DataFrame) -> list[dict]:
    """Una recomendación por caso de uso, con la evidencia que la respalda.

    Corre el pipeline completo (priorización + value realization +
    duplicación) internamente -- no depende de que el caller ya haya llamado
    a las otras tools. Cada dict devuelto trae `action`, `reason` (texto ya
    armado con los valores reales, no una plantilla vacía) y `evidence` (los
    números crudos, para que el reporte -- Task 11 -- o el agente los citen
    literal).
    """
    scored = compute_priority_scores(df)
    scored = compute_value_realization_status(scored)
    duplicated_ids = duplicated_use_case_ids(df)

    recommendations = []
    for _, row in scored.iterrows():
        use_case_id = row["use case id"]
        title = row["title"]
        priority_score = row["priority_score"]
        value_status = row["value_status"]
        evidence = {
            "priority_score": priority_score,
            "value_status": value_status,
            "current_stage_name": row["current stage name"],
        }

        if use_case_id in duplicated_ids:
            overlaps = get_use_case_overlap_detail(df, use_case_id)
            other_ids = sorted(
                {
                    o["use_case_id_b"] if o["use_case_id_a"] == use_case_id else o["use_case_id_a"]
                    for o in overlaps
                }
            )
            action = "Consolidate"
            reason = (
                f"Overlap significativo con {', '.join(other_ids)} "
                f"(similarity={overlaps[0]['similarity_score']}, dimensiones "
                f"compartidas={overlaps[0]['shared_dimensions']}) -- consolidar en "
                "una sola iniciativa en vez de mantener ambas por separado."
            )
            evidence["duplicate_of"] = other_ids
        elif priority_score < _LOW_PRIORITY_THRESHOLD and (
            value_status in _VALUE_AT_RISK or row["current stage name"] in _PRE_INVESTMENT_STAGES
        ):
            action = "Discontinue"
            if value_status in _VALUE_AT_RISK:
                reason = (
                    f"priority_score bajo ({priority_score}/100, umbral "
                    f"{_LOW_PRIORITY_THRESHOLD}) y value_status={value_status}: no "
                    "es prioritario y no está entregando el valor esperado."
                )
            else:
                reason = (
                    f"priority_score bajo ({priority_score}/100, umbral "
                    f"{_LOW_PRIORITY_THRESHOLD}) y todavía en "
                    f"{row['current stage name']}, sin inversión real hundida "
                    "todavía: no vale la pena seguir madurando esta idea."
                )
        elif value_status in _VALUE_AT_RISK:
            action = "Reduce Investment"
            reason = (
                f"value_status={value_status} pese a un priority_score razonable "
                f"({priority_score}/100) -- mantener el caso pero pausar/reducir "
                "inversión adicional hasta resolver el problema de valor."
            )
        elif priority_score >= _HIGH_PRIORITY_THRESHOLD and value_status == "on_track":
            action = "Scale"
            reason = (
                f"priority_score alto ({priority_score}/100, umbral "
                f"{_HIGH_PRIORITY_THRESHOLD}) y value_status=on_track: candidato "
                "real a más inversión/rollout."
            )
        else:
            action = "Continue/Monitor"
            reason = (
                f"priority_score medio ({priority_score}/100) y "
                f"value_status={value_status}: seguir monitoreando, sin acción "
                "urgente."
            )

        recommendations.append(
            {
                "use_case_id": use_case_id,
                "title": title,
                "action": action,
                "reason": reason,
                "evidence": evidence,
            }
        )
    return recommendations


def _render_recommendations(recs: list[dict], action_filter: str | None = None) -> str:
    filtered = [r for r in recs if action_filter is None or r["action"] == action_filter]
    if not filtered:
        return f"Ningún caso de uso con acción recomendada '{action_filter}'."
    lines = []
    for r in filtered:
        lines.append(f"- {r['use_case_id']} ({r['title']}): {r['action']} — {r['reason']}")
    return "\n".join(lines)


def build_recommendation_tools(df: pd.DataFrame) -> list:
    """Arma la lista de tools LangChain del agente de recomendación, atadas a `df`.

    Este agente es el único que compone las tres tools anteriores -- su
    trabajo, per `agents/portfolio_recommendation.py`, es puramente narrar lo
    que esta tool ya calculó y decidió, no volver a evaluarlo.

    Import de `langchain_core.tools.tool` diferido a acá adentro -- ver la
    misma nota en `prioritization_tools.build_prioritization_tools`.
    """
    from langchain_core.tools import tool

    recommendations = generate_portfolio_recommendations(df)

    def get_portfolio_recommendations_tool(action: str = "") -> str:
        """Devuelve las recomendaciones del portfolio completo, o filtradas por acción si se pasa `action` (uno de "Scale", "Consolidate", "Reduce Investment", "Discontinue", "Continue/Monitor")."""
        return _render_recommendations(recommendations, action or None)

    def explain_recommendation_tool(use_case_id: str) -> str:
        """Explica la recomendación y evidencia de un caso de uso puntual, dado su `use case id`."""
        matches = [r for r in recommendations if r["use_case_id"] == use_case_id]
        if not matches:
            return f"No se encontró ningún caso de uso con id '{use_case_id}'."
        r = matches[0]
        return (
            f"{r['use_case_id']} — {r['title']}: {r['action']}\n"
            f"  Razón: {r['reason']}\n"
            f"  Evidencia: {r['evidence']}"
        )

    return [
        tool(safe_tool(get_portfolio_recommendations_tool)),
        tool(safe_tool(explain_recommendation_tool)),
    ]

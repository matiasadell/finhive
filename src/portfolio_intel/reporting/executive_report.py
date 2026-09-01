from __future__ import annotations

import pandas as pd

from portfolio_intel.tools.duplication_tools import find_duplicate_use_cases
from portfolio_intel.tools.prioritization_tools import compute_priority_scores, get_top_priorities
from portfolio_intel.tools.recommendation_tools import generate_portfolio_recommendations
from portfolio_intel.tools.value_realization_tools import (
    compute_value_realization_status,
    get_at_risk_use_cases,
)


def _render_summary(recommendations: list[dict]) -> str:
    counts: dict[str, int] = {}
    for r in recommendations:
        counts[r["action"]] = counts.get(r["action"], 0) + 1
    total = len(recommendations)
    lines = [
        f"Portfolio analizado: **{total} casos de uso de IA**.",
        "",
        "| Acción recomendada | Casos de uso |",
        "|---|---|",
    ]
    for action in ("Scale", "Continue/Monitor", "Reduce Investment", "Consolidate", "Discontinue"):
        lines.append(f"| {action} | {counts.get(action, 0)} |")
    return "\n".join(lines)


def _render_top_priorities(df: pd.DataFrame, n: int = 8) -> str:
    top = get_top_priorities(df, n)
    lines = [
        "| Use Case ID | Título | priority_score | Stage | Confidence |",
        "|---|---|---|---|---|",
    ]
    for _, row in top.iterrows():
        lines.append(
            f"| {row['use case id']} | {row['title']} | {row['priority_score']}/100 | "
            f"{row['current stage name']} | {row['confidence level']} |"
        )
    return "\n".join(lines)


def _render_duplication(df: pd.DataFrame) -> str:
    pairs = find_duplicate_use_cases(df)
    if not pairs:
        return "No se encontraron casos de uso con overlap significativo en este portfolio."
    lines = []
    for p in pairs:
        lines.append(
            f"- **{p['use_case_id_a']}** ({p['title_a']}) <-> **{p['use_case_id_b']}** "
            f"({p['title_b']}) — similarity={p['similarity_score']}, "
            f"dimensiones compartidas: {', '.join(p['shared_dimensions'])}"
        )
    return "\n".join(lines)


def _render_value_risks(df: pd.DataFrame) -> str:
    at_risk = get_at_risk_use_cases(df)
    if at_risk.empty:
        return "Ningún caso de uso aprobado está actualmente at_risk/off_track."
    lines = []
    for _, row in at_risk.iterrows():
        barrier = row["insight learned or barriers"]
        barrier = "(sin nota registrada)" if pd.isna(barrier) or not str(barrier).strip() else barrier
        lines.append(
            f"- **{row['use case id']}** ({row['title']}) — value_status="
            f"**{row['value_status']}**. {barrier}"
        )
    return "\n".join(lines)


def _render_recommendations(recommendations: list[dict]) -> str:
    sections = []
    for action in ("Scale", "Consolidate", "Reduce Investment", "Discontinue", "Continue/Monitor"):
        rows = [r for r in recommendations if r["action"] == action]
        if not rows:
            continue
        lines = [f"### {action} ({len(rows)})"]
        for r in rows:
            lines.append(f"- **{r['use_case_id']}** ({r['title']}): {r['reason']}")
        sections.append("\n".join(lines))
    return "\n\n".join(sections)


def render_executive_report(df: pd.DataFrame) -> str:
    scored = compute_priority_scores(df)
    scored = compute_value_realization_status(scored)
    recommendations = generate_portfolio_recommendations(df)

    return "\n\n".join(
        [
            "# Portfolio Intel — Reporte Ejecutivo",
            (
                "Inteligencia de portfolio de IA para leadership: priorización, "
                "reuso/duplicación, value realization y recomendaciones de "
                "inversión. Generado de forma determinista a partir del AI Use "
                "Case Inventory -- cada afirmación de este reporte es "
                "trazable a una fila/columna concreta del dataset fuente. "
                "Este es un sistema de research/decisión de negocio, no "
                "ejecución real de inversión."
            ),
            "## Resumen ejecutivo",
            _render_summary(recommendations),
            "## Top prioridades",
            _render_top_priorities(scored),
            "## Reuso y duplicación",
            _render_duplication(df),
            "## Riesgos de value realization",
            _render_value_risks(scored),
            "## Recomendaciones por caso de uso",
            _render_recommendations(recommendations),
        ]
    )

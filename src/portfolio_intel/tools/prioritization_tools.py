from __future__ import annotations

import pandas as pd

from portfolio_intel.tools.wrappers import safe_tool

# Pesos del composite (35% impacto, 25% eficiencia de inversión, 20%
# confianza, 10% stage, 10% escalabilidad). Nunca calculado por el LLM.
_WEIGHTS = {
    "impact": 0.35,
    "investment_efficiency": 0.25,
    "confidence": 0.20,
    "stage_proximity": 0.10,
    "scalability": 0.10,
}

_CONFIDENCE_SCORE = {"Low": 25.0, "Medium": 60.0, "High": 100.0}
_SCALABILITY_SCORE = {"Low": 25.0, "Medium": 60.0, "High": 100.0}
_STAGE_PROXIMITY_SCORE = {
    "Ideation": 10.0,
    "On Hold": 15.0,
    "Intake Review": 25.0,
    "Pilot": 50.0,
    "Limited Production": 75.0,
    "Full Production": 100.0,
}


def _min_max_normalize(series: pd.Series) -> pd.Series:
    low, high = series.min(), series.max()
    if high == low:
        return pd.Series(50.0, index=series.index)
    return (series - low) / (high - low) * 100.0


def compute_priority_scores(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["impact_score"] = _min_max_normalize(out["max impact"])
    investment_efficiency = out["max impact"] / out["projected total investment"].replace(0, pd.NA)
    out["investment_efficiency_score"] = _min_max_normalize(investment_efficiency.fillna(0))
    out["confidence_score"] = out["confidence level"].map(_CONFIDENCE_SCORE).fillna(0.0)
    out["stage_proximity_score"] = out["current stage name"].map(_STAGE_PROXIMITY_SCORE).fillna(0.0)
    out["scalability_score"] = out["scalability"].map(_SCALABILITY_SCORE).fillna(0.0)
    out["priority_score"] = (
        out["impact_score"] * _WEIGHTS["impact"]
        + out["investment_efficiency_score"] * _WEIGHTS["investment_efficiency"]
        + out["confidence_score"] * _WEIGHTS["confidence"]
        + out["stage_proximity_score"] * _WEIGHTS["stage_proximity"]
        + out["scalability_score"] * _WEIGHTS["scalability"]
    ).round(1)
    return out


def get_top_priorities(df: pd.DataFrame, n: int = 5) -> pd.DataFrame:
    scored = compute_priority_scores(df) if "priority_score" not in df.columns else df
    return scored.sort_values("priority_score", ascending=False).head(n)


def explain_priority_score(df: pd.DataFrame, use_case_id: str) -> str:
    scored = compute_priority_scores(df) if "priority_score" not in df.columns else df
    rows = scored[scored["use case id"] == use_case_id]
    if rows.empty:
        return f"No se encontró ningún caso de uso con id '{use_case_id}'."
    row = rows.iloc[0]
    return (
        f"{use_case_id} — {row['title']}: priority_score = {row['priority_score']}/100\n"
        f"  - impacto: max impact=${row['max impact']:,.0f} -> "
        f"{row['impact_score']:.1f}/100 (peso {_WEIGHTS['impact']:.0%})\n"
        f"  - eficiencia de inversión: max impact / projected total investment "
        f"(${row['projected total investment']:,.0f}) -> "
        f"{row['investment_efficiency_score']:.1f}/100 (peso {_WEIGHTS['investment_efficiency']:.0%})\n"
        f"  - confianza: {row['confidence level']} -> "
        f"{row['confidence_score']:.0f}/100 (peso {_WEIGHTS['confidence']:.0%})\n"
        f"  - proximidad de stage: {row['current stage name']} -> "
        f"{row['stage_proximity_score']:.0f}/100 (peso {_WEIGHTS['stage_proximity']:.0%})\n"
        f"  - escalabilidad: {row['scalability']} -> "
        f"{row['scalability_score']:.0f}/100 (peso {_WEIGHTS['scalability']:.0%})"
    )


def _render_priority_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "Ningún caso de uso cumple el criterio."
    lines = []
    for _, row in df.iterrows():
        lines.append(
            f"- {row['use case id']} ({row['title']}): priority_score={row['priority_score']}/100, "
            f"stage={row['current stage name']}, confidence={row['confidence level']}"
        )
    return "\n".join(lines)


def build_prioritization_tools(df: pd.DataFrame) -> list:
    from langchain_core.tools import tool

    scored_df = compute_priority_scores(df)

    def get_top_priorities_tool(n: int = 5) -> str:
        """Devuelve los `n` casos de uso con mayor priority_score, con su score."""
        return _render_priority_table(get_top_priorities(scored_df, n))

    def explain_priority_score_tool(use_case_id: str) -> str:
        """Explica el breakdown del priority_score de un caso de uso puntual, dado su `use case id` (ej. "UC-003")."""
        return explain_priority_score(scored_df, use_case_id)

    def get_all_priority_scores_tool() -> str:
        """Devuelve el priority_score de todos los casos de uso del portfolio, descendente."""
        return _render_priority_table(scored_df.sort_values("priority_score", ascending=False))

    return [
        tool(safe_tool(get_top_priorities_tool)),
        tool(safe_tool(explain_priority_score_tool)),
        tool(safe_tool(get_all_priority_scores_tool)),
    ]

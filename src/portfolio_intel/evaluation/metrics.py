from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from portfolio_intel.tools.duplication_tools import find_duplicate_use_cases
from portfolio_intel.tools.prioritization_tools import compute_priority_scores, get_top_priorities
from portfolio_intel.tools.recommendation_tools import generate_portfolio_recommendations
from portfolio_intel.tools.value_realization_tools import compute_value_realization_status


@dataclass
class EvalContext:
    scored_df: pd.DataFrame
    duplicate_pairs: list[dict]
    recommendations: dict[str, dict]  # use_case_id -> recommendation dict

    @classmethod
    def build(cls, df: pd.DataFrame) -> "EvalContext":
        scored = compute_priority_scores(df)
        scored = compute_value_realization_status(scored)
        pairs = find_duplicate_use_cases(df)
        recs = {r["use_case_id"]: r for r in generate_portfolio_recommendations(df)}
        return cls(scored_df=scored, duplicate_pairs=pairs, recommendations=recs)


def _check_duplicate_pair(item: dict, ctx: EvalContext) -> tuple[bool, str]:
    a, b = item["use_case_id"], item["other_use_case_id"]
    found = any(
        {p["use_case_id_a"], p["use_case_id_b"]} == {a, b} for p in ctx.duplicate_pairs
    )
    detail = f"par {a}/{b} {'encontrado' if found else 'NO encontrado'} en find_duplicate_use_cases"
    return found, detail


def _check_top_priority(item: dict, ctx: EvalContext) -> tuple[bool, str]:
    top_n = item.get("top_n", 5)
    top = get_top_priorities(ctx.scored_df, top_n)
    found = item["use_case_id"] in set(top["use case id"])
    detail = f"{item['use_case_id']} {'está' if found else 'NO está'} en el top {top_n} de priority_score"
    return found, detail


def _check_value_status_in(item: dict, ctx: EvalContext) -> tuple[bool, str]:
    rows = ctx.scored_df[ctx.scored_df["use case id"] == item["use_case_id"]]
    if rows.empty:
        return False, f"{item['use_case_id']} no existe en el dataset"
    status = rows.iloc[0]["value_status"]
    allowed = item["allowed_statuses"]
    ok = status in allowed
    detail = f"{item['use_case_id']}: value_status={status} (esperado uno de {allowed})"
    return ok, detail


def _check_recommended_action(item: dict, ctx: EvalContext) -> tuple[bool, str]:
    rec = ctx.recommendations.get(item["use_case_id"])
    if rec is None:
        return False, f"{item['use_case_id']} no tiene recomendación"
    ok = rec["action"] == item["expected_action"]
    detail = f"{item['use_case_id']}: action={rec['action']} (esperado {item['expected_action']})"
    return ok, detail


_CHECKS = {
    "duplicate_pair": _check_duplicate_pair,
    "top_priority": _check_top_priority,
    "value_status_in": _check_value_status_in,
    "recommended_action": _check_recommended_action,
}


def run_golden_set(golden_set: list[dict], df: pd.DataFrame) -> list[dict]:
    ctx = EvalContext.build(df)
    results = []
    for item in golden_set:
        check_fn = _CHECKS[item["check"]]
        passed, detail = check_fn(item, ctx)
        results.append(
            {"id": item["id"], "check": item["check"], "passed": passed, "detail": detail}
        )
    return results


def pass_rate(results: list[dict]) -> float:
    if not results:
        return 0.0
    return sum(1 for r in results if r["passed"]) / len(results)

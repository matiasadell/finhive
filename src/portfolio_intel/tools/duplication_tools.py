from __future__ import annotations

import re

import pandas as pd

from portfolio_intel.tools.wrappers import safe_tool

_STOPWORDS = {
    "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del", "al",
    "a", "en", "y", "o", "que", "con", "para", "por", "su", "sus", "es", "se",
    "no", "lo", "mas", "sin", "hoy",
}

_GROUPING_COLUMNS = ["domain", "value chain", "sub value chain", "focus area"]


def _tokenize(text: str) -> set[str]:
    words = re.findall(r"[a-záéíóúñ]+", str(text).lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 2}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def find_duplicate_use_cases(df: pd.DataFrame, similarity_threshold: float = 0.4) -> list[dict]:
    records = df.to_dict("records")
    tokens_by_id = {
        r["use case id"]: _tokenize(f"{r['business challenge']} {r['target state']}")
        for r in records
    }
    pairs = []
    for i, a in enumerate(records):
        for b in records[i + 1 :]:
            shared_dims = [c for c in _GROUPING_COLUMNS if a[c] == b[c]]
            if not shared_dims:
                continue
            score = _jaccard(tokens_by_id[a["use case id"]], tokens_by_id[b["use case id"]])
            if score >= similarity_threshold:
                pairs.append(
                    {
                        "use_case_id_a": a["use case id"],
                        "title_a": a["title"],
                        "business_challenge_a": a["business challenge"],
                        "use_case_id_b": b["use case id"],
                        "title_b": b["title"],
                        "business_challenge_b": b["business challenge"],
                        "similarity_score": round(score, 2),
                        "shared_dimensions": shared_dims,
                    }
                )
    return sorted(pairs, key=lambda p: p["similarity_score"], reverse=True)


def get_use_case_overlap_detail(df: pd.DataFrame, use_case_id: str) -> list[dict]:
    all_pairs = find_duplicate_use_cases(df)
    return [
        p for p in all_pairs if use_case_id in (p["use_case_id_a"], p["use_case_id_b"])
    ]


def duplicated_use_case_ids(df: pd.DataFrame) -> set[str]:
    pairs = find_duplicate_use_cases(df)
    ids: set[str] = set()
    for p in pairs:
        ids.add(p["use_case_id_a"])
        ids.add(p["use_case_id_b"])
    return ids


def _render_pairs(pairs: list[dict]) -> str:
    if not pairs:
        return "No se encontraron casos de uso con overlap significativo."
    lines = []
    for p in pairs:
        lines.append(
            f"- {p['use_case_id_a']} ({p['title_a']}) <-> {p['use_case_id_b']} ({p['title_b']}): "
            f"similarity={p['similarity_score']}, dimensiones compartidas={p['shared_dimensions']}\n"
            f"    {p['use_case_id_a']} business_challenge: {p['business_challenge_a']}\n"
            f"    {p['use_case_id_b']} business_challenge: {p['business_challenge_b']}"
        )
    return "\n".join(lines)


def build_duplication_tools(df: pd.DataFrame) -> list:
    from langchain_core.tools import tool

    def find_duplicate_use_cases_tool() -> str:
        """Devuelve todos los pares de casos de uso del portfolio con overlap significativo (posible duplicado/reuso)."""
        return _render_pairs(find_duplicate_use_cases(df))

    def get_use_case_overlap_detail_tool(use_case_id: str) -> str:
        """Devuelve el detalle de overlap de un caso de uso puntual, dado su `use case id` (ej. "UC-007")."""
        return _render_pairs(get_use_case_overlap_detail(df, use_case_id))

    return [
        tool(safe_tool(find_duplicate_use_cases_tool)),
        tool(safe_tool(get_use_case_overlap_detail_tool)),
    ]

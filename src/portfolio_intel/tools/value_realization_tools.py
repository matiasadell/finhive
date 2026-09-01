"""Value realization determinista: on_track / at_risk / off_track por caso de uso.

Mismo principio que el resto de `tools/`: el status lo calculan estas
funciones sobre columnas reales, nunca lo asume el LLM. Se combinan tres
señales de riesgo binarias, cada una auditable de forma independiente:

1. **cost_overrun** — `projected total investment` supera en más de 30% a
   `planned investment`.
2. **timeline_breach** — `value return begins in` ya pasó (relativo a
   `as_of`) y el caso todavía está en un stage "pre-valor"
   (`Ideation`/`Intake Review`/`Pilot`/`On Hold` -- `Limited Production` y
   `Full Production` ya están generando valor real, así que no cuentan para
   esta señal aunque su fecha de inicio también haya pasado).
3. **documented_barrier** — `insight learned or barriers` tiene texto no
   vacío (alguien ya documentó un bloqueo concreto).

`value_status` = `off_track` si hay 2+ señales, `at_risk` si hay exactamente
1, `on_track` si no hay ninguna. `as_of` default es `date.today()` -- el
dataset sintético (`data/synthetic.py`) fue construido asumiendo "hoy" =
2026-09-01 para el caso `UC-015`; si se regenera el dataset mucho después de
esa fecha, revisar que las señales sigan disparando donde corresponde.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from portfolio_intel.tools.wrappers import safe_tool

_COST_OVERRUN_THRESHOLD = 1.3  # 30%+ sobre lo planeado
_PRE_VALUE_STAGES = {"Ideation", "Intake Review", "Pilot", "On Hold"}


def _cost_overrun(row: pd.Series) -> bool:
    planned = row["planned investment"]
    if not planned:
        return False
    return row["projected total investment"] > planned * _COST_OVERRUN_THRESHOLD


def _timeline_breach(row: pd.Series, as_of: date) -> bool:
    if row["current stage name"] not in _PRE_VALUE_STAGES:
        return False
    begins = pd.to_datetime(row["value return begins in"]).date()
    return begins < as_of


def _barrier_text(row: pd.Series, empty_label: str) -> str:
    value = row["insight learned or barriers"]
    return empty_label if pd.isna(value) or not str(value).strip() else str(value)


def _documented_barrier(row: pd.Series) -> bool:
    value = row["insight learned or barriers"]
    # pandas lee una celda vacía del CSV como NaN, no como string vacío --
    # `str(nan)` es la string no-vacía "nan", así que hay que chequear NaN
    # explícito antes de castear a string (si no, todas las filas sin
    # barrera documentada disparaban esta señal igual).
    if pd.isna(value):
        return False
    return bool(str(value).strip())


def compute_value_realization_status(df: pd.DataFrame, as_of: date | None = None) -> pd.DataFrame:
    """Agrega `value_status` + las 3 columnas de señal (booleanas) al df.

    No muta `df` -- devuelve una copia.
    """
    as_of = as_of or date.today()
    out = df.copy()
    out["signal_cost_overrun"] = out.apply(_cost_overrun, axis=1)
    out["signal_timeline_breach"] = out.apply(lambda r: _timeline_breach(r, as_of), axis=1)
    out["signal_documented_barrier"] = out.apply(_documented_barrier, axis=1)
    signal_count = (
        out["signal_cost_overrun"].astype(int)
        + out["signal_timeline_breach"].astype(int)
        + out["signal_documented_barrier"].astype(int)
    )
    out["value_status"] = signal_count.map(
        lambda n: "off_track" if n >= 2 else ("at_risk" if n == 1 else "on_track")
    )
    return out


def get_at_risk_use_cases(df: pd.DataFrame, as_of: date | None = None) -> pd.DataFrame:
    """Casos de uso con `value_status` in (`at_risk`, `off_track`)."""
    scored = (
        compute_value_realization_status(df, as_of)
        if "value_status" not in df.columns
        else df
    )
    return scored[scored["value_status"].isin(["at_risk", "off_track"])]


def explain_value_status(df: pd.DataFrame, use_case_id: str, as_of: date | None = None) -> str:
    """Renderiza qué señales dispararon (o no) el `value_status` de un caso."""
    scored = (
        compute_value_realization_status(df, as_of)
        if "value_status" not in df.columns
        else df
    )
    rows = scored[scored["use case id"] == use_case_id]
    if rows.empty:
        return f"No se encontró ningún caso de uso con id '{use_case_id}'."
    row = rows.iloc[0]
    lines = [f"{use_case_id} — {row['title']}: value_status = {row['value_status']}"]
    lines.append(
        f"  - cost_overrun: {row['signal_cost_overrun']} "
        f"(planned investment=${row['planned investment']:,.0f}, "
        f"projected total investment=${row['projected total investment']:,.0f})"
    )
    lines.append(
        f"  - timeline_breach: {row['signal_timeline_breach']} "
        f"(current stage name={row['current stage name']}, "
        f"value return begins in={row['value return begins in']})"
    )
    lines.append(
        f"  - documented_barrier: {row['signal_documented_barrier']} "
        f"(insight learned or barriers: "
        f"{_barrier_text(row, '(vacío)')})"
    )
    return "\n".join(lines)


def _render_at_risk_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "Ningún caso de uso está at_risk/off_track según las señales actuales."
    lines = []
    for _, row in df.iterrows():
        lines.append(
            f"- {row['use case id']} ({row['title']}): value_status={row['value_status']} "
            f"(barrera: {_barrier_text(row, '(sin nota registrada)')})"
        )
    return "\n".join(lines)


def build_value_realization_tools(df: pd.DataFrame) -> list:
    """Arma la lista de tools LangChain del agente de value realization, atadas a `df`.

    Import de `langchain_core.tools.tool` diferido a acá adentro -- ver la
    misma nota en `prioritization_tools.build_prioritization_tools`.
    """
    from langchain_core.tools import tool
    scored_df = compute_value_realization_status(df)

    def get_at_risk_use_cases_tool() -> str:
        """Devuelve los casos de uso con value_status at_risk u off_track, con la barrera documentada."""
        return _render_at_risk_table(get_at_risk_use_cases(scored_df))

    def explain_value_status_tool(use_case_id: str) -> str:
        """Explica qué señales de riesgo dispararon el value_status de un caso, dado su `use case id`."""
        return explain_value_status(scored_df, use_case_id)

    def get_all_value_statuses_tool() -> str:
        """Devuelve el value_status de todos los casos de uso del portfolio."""
        lines = [
            f"- {row['use case id']} ({row['title']}): value_status={row['value_status']}"
            for _, row in scored_df.iterrows()
        ]
        return "\n".join(lines)

    return [
        tool(safe_tool(get_at_risk_use_cases_tool)),
        tool(safe_tool(explain_value_status_tool)),
        tool(safe_tool(get_all_value_statuses_tool)),
    ]

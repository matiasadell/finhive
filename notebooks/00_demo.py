"""Demo de Portfolio Intel: 4 escenarios end-to-end, con outputs reales.

A diferencia del `00_demo.py` de finhive (celdas de notebook `# COMMAND
----------`, pensado para correr solo dentro de un notebook de Databricks
Repos vía `dbutils`), este es un script Python plano -- corre tal cual con
`python notebooks/00_demo.py` en esta máquina de desarrollo, y también sirve
sin cambios como notebook de Databricks Repos (`Run All`) una vez ahí, sin
depender de `dbutils` para nada de su lógica propia.

Cada escenario hace dos cosas:
1. Invoca el grafo completo de agentes (`build_top_supervisor`) -- esto
   necesita un LLM real vía Databricks, así que en esta máquina de
   desarrollo falla en la llamada al modelo (ver
   `prompts/constraints_environment.md`); el fallo se atrapa y se explica,
   no se deja como traceback crudo.
2. Llama `render_executive_report` directo -- 100% determinista, sin LLM,
   corre siempre. Es la parte que de verdad se puede verificar acá.

Los outputs (transcript del grafo si corrió, y el reporte ejecutivo) se
escriben a `outputs/demo_scenario_{n}_*.md`.
"""

from __future__ import annotations

from pathlib import Path

from portfolio_intel.data.store import load_portfolio_data
from portfolio_intel.graph.top_supervisor import build_top_supervisor
from portfolio_intel.reporting.executive_report import render_executive_report

_OUTPUTS_DIR = Path(__file__).resolve().parents[1] / "outputs"

_SCENARIOS = [
    (
        "quarterly_prioritization",
        "Tenemos presupuesto limitado para el próximo trimestre. ¿Qué casos de uso "
        "de IA deberíamos priorizar primero?",
    ),
    (
        "reuse_check",
        "Estamos por lanzar un nuevo chatbot de status de claims para la región "
        "Este. ¿Hay algo parecido ya en marcha en el portfolio?",
    ),
    (
        "value_realization_review",
        "¿Qué casos de uso ya aprobados no están en camino de realizar el valor "
        "que prometieron?",
    ),
    (
        "executive_recommendation",
        "Dame la recomendación completa del portfolio: qué escalar, consolidar, "
        "reducir o discontinuar.",
    ),
]


def _run_agent_scenario(graph, question: str) -> str:
    """Invoca el grafo; devuelve el transcript o una explicación del fallo esperado."""
    try:
        result = graph.invoke({"messages": [("user", question)]})
        agent_messages = [
            m
            for m in result["messages"]
            if getattr(m, "name", None) and str(m.name).endswith("_agent")
        ]
        lines = [f"Agentes invocados: {[m.name for m in agent_messages]}", ""]
        lines.append(f"Respuesta final:\n{result['messages'][-1].content}")
        return "\n".join(lines)
    except Exception as e:  # noqa: BLE001 - a propósito, ver docstring del módulo
        return (
            "⚠️ No se pudo invocar el grafo de agentes (esperado en esta máquina "
            "de desarrollo, sin conexión a Databricks -- ver "
            f"prompts/constraints_environment.md).\n\nError: {type(e).__name__}: {e}"
        )


def main() -> None:
    _OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

    df = load_portfolio_data().get_use_cases()
    print(f"Portfolio cargado: {len(df)} casos de uso.\n")

    print("Generando reporte ejecutivo (determinista, sin LLM)...")
    report = render_executive_report(df)
    report_path = _OUTPUTS_DIR / "demo_executive_report.md"
    report_path.write_text(report, encoding="utf-8")
    print(f"  -> {report_path}\n")

    graph = build_top_supervisor(df)

    for i, (name, question) in enumerate(_SCENARIOS, start=1):
        print(f"Escenario {i}/{len(_SCENARIOS)}: {name}")
        print(f"  Pregunta: {question}")
        transcript = _run_agent_scenario(graph, question)
        out_path = _OUTPUTS_DIR / f"demo_scenario_{i}_{name}.md"
        out_path.write_text(f"# Escenario: {name}\n\n**Pregunta:** {question}\n\n{transcript}\n", encoding="utf-8")
        print(f"  -> {out_path}\n")

    print("Demo completa. Ver outputs/ para los artefactos generados.")


if __name__ == "__main__":
    main()

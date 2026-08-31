"""Sub-supervisor de Macro: compone los 3 workers con `langgraph_supervisor`.

Mismo patrón que la sección "Multi Agent Supervisor" del notebook de
referencia del bootcamp: un supervisor central recibe la tarea completa,
decide qué worker la atiende, y devuelve la respuesta integrada — los
workers no se hablan entre sí directamente.
"""

from __future__ import annotations

from finhive.agents.macro.workers import build_macro_workers
from finhive.config.settings import get_chat_model


def build_macro_supervisor():
    """Compila el grafo del sub-supervisor de Macro, listo para invocar.

    El ejemplo concreto de FEDFUNDS en el prompt de abajo se agregó por el
    mismo hallazgo que ya se documentó en `top_supervisor._make_supervisor_node`
    (ADR 0015): visto en vivo, este supervisor a veces volvía a invocar a un
    worker que ya había dado el dato pedido, en vez de sintetizar y cerrar.
    """
    from langgraph_supervisor import create_supervisor

    workers = build_macro_workers()

    supervisor = create_supervisor(
        model=get_chat_model("supervisor"),
        agents=[
            workers["rates_worker"],
            workers["inflation_worker"],
            workers["indicators_worker"],
        ],
        prompt=(
            "Sos el supervisor del equipo de Macro & Política Monetaria de FinHive. "
            "Coordinás tres analistas: rates_worker (tasas de interés / banco "
            "central), inflation_worker (inflación / CPI) e indicators_worker "
            "(GDP, empleo, indicadores generales). Asigná cada parte de la "
            "pregunta al analista correspondiente, uno a la vez, y después "
            "sintetizá sus respuestas en un análisis macro coherente. No "
            "inventes datos vos mismo — todo dato numérico tiene que venir de "
            "un analista. Una vez que un analista ya te dio el dato pedido, "
            "respondé vos mismo con la síntesis final — no lo vuelvas a "
            "invocar pidiendo que confirme o repita. Ejemplo concreto: si "
            "preguntan la tasa de fondos federales y rates_worker ya "
            "respondió 'La tasa de fondos federales (FEDFUNDS) es 3.63% al "
            "2026-07-01', esa es la respuesta final — sintetizala y cerrá "
            "ahí. Este es un sistema de research, no de asesoramiento "
            "financiero: no des recomendaciones de inversión."
        ),
        add_handoff_back_messages=True,
        output_mode="full_history",
    )
    return supervisor.compile()

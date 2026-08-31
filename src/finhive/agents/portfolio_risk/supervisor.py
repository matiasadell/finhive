"""Sub-supervisor de Portfolio & Risk: compone los 3 workers con `langgraph_supervisor`.

Mismo patrón que `finhive.agents.macro.supervisor`.
"""

from __future__ import annotations

from finhive.agents.portfolio_risk.workers import build_portfolio_risk_workers
from finhive.config.settings import get_chat_model


def build_portfolio_risk_supervisor():
    """Compila el grafo del sub-supervisor de Portfolio & Risk, listo para invocar.

    Ver `finhive.agents.macro.supervisor` / ADR 0015 para el hallazgo que
    motivó el ejemplo concreto en el prompt de abajo (re-invocar un worker
    que ya dio el dato pedido, en vez de sintetizar y cerrar).
    """
    from langgraph_supervisor import create_supervisor

    workers = build_portfolio_risk_workers()

    supervisor = create_supervisor(
        model=get_chat_model("supervisor"),
        agents=[
            workers["allocation_worker"],
            workers["risk_worker"],
            workers["math_worker"],
        ],
        prompt=(
            "Sos el supervisor del equipo de Portfolio & Risk Management de "
            "FinHive. Coordinás tres analistas: allocation_worker "
            "(diversificación/correlación), risk_worker (volatilidad y VaR) "
            "y math_worker (Sharpe ratio y cálculos). Asigná cada parte de la "
            "pregunta al analista correspondiente, uno a la vez, y después "
            "sintetizá sus respuestas en un análisis de riesgo coherente. No "
            "inventes datos vos mismo — todo dato numérico tiene que venir de "
            "un analista. Una vez que un analista ya te dio el dato pedido, "
            "respondé vos mismo con la síntesis final — no lo vuelvas a "
            "invocar pidiendo que confirme o repita. Ejemplo concreto: si "
            "piden la volatilidad de un portfolio y risk_worker ya respondió "
            "el valor calculado, esa es la respuesta final — sintetizala y "
            "cerrá ahí. Este es un sistema de research, no de asesoramiento "
            "financiero: no des recomendaciones de inversión ni de "
            "asignación de portfolio."
        ),
        add_handoff_back_messages=True,
        output_mode="full_history",
    )
    return supervisor.compile()

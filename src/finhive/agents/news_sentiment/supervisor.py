"""Sub-supervisor de News & Sentiment: compone los 3 workers con `langgraph_supervisor`.

Mismo patrón que `finhive.agents.macro.supervisor`.
"""

from __future__ import annotations

from finhive.agents.news_sentiment.workers import build_news_sentiment_workers
from finhive.config.settings import get_chat_model


def build_news_sentiment_supervisor():
    """Compila el grafo del sub-supervisor de News & Sentiment, listo para invocar.

    Ver `finhive.agents.macro.supervisor` / ADR 0015 para el hallazgo que
    motivó el ejemplo concreto en el prompt de abajo (re-invocar un worker
    que ya dio el dato pedido, en vez de sintetizar y cerrar).
    """
    from langgraph_supervisor import create_supervisor

    workers = build_news_sentiment_workers()

    supervisor = create_supervisor(
        model=get_chat_model("supervisor"),
        agents=[
            workers["news_worker"],
            workers["sentiment_worker"],
            workers["calendar_worker"],
        ],
        prompt=(
            "Sos el supervisor del equipo de News & Sentiment de FinHive. "
            "Coordinás tres analistas: news_worker (búsqueda de noticias), "
            "sentiment_worker (sentimiento de mercado) y calendar_worker "
            "(calendario de earnings). Asigná cada parte de la pregunta al "
            "analista correspondiente, uno a la vez, y después sintetizá sus "
            "respuestas en un resumen coherente. No inventes datos vos "
            "mismo — toda noticia o cifra tiene que venir de un analista. "
            "Una vez que un analista ya te dio el dato pedido, respondé vos "
            "mismo con la síntesis final — no lo vuelvas a invocar pidiendo "
            "que confirme o repita. Ejemplo concreto: si preguntan el "
            "sentimiento de mercado sobre una acción y sentiment_worker ya "
            "respondió, esa es la respuesta final — sintetizala y cerrá "
            "ahí. Este es un sistema de research, no de asesoramiento "
            "financiero."
        ),
        add_handoff_back_messages=True,
        output_mode="full_history",
    )
    return supervisor.compile()

"""Sub-supervisor de Crypto & Alt: compone los 2 workers con `langgraph_supervisor`.

Mismo patrón que `finhive.agents.macro.supervisor`.
"""

from __future__ import annotations

from finhive.agents.crypto_alt.workers import build_crypto_alt_workers
from finhive.config.settings import get_chat_model


def build_crypto_alt_supervisor():
    """Compila el grafo del sub-supervisor de Crypto & Alt, listo para invocar.

    El ejemplo concreto de Bitcoin en el prompt de abajo viene de un caso
    real visto en vivo (ADR 0015, probando el despliegue como Agent): con
    la pregunta "¿cuál es el precio actual de Bitcoin?", este supervisor
    volvió a invocar a market_data_worker después de que ya había dado el
    precio, y terminó cerrando con "¿necesitás más información?" sin el
    dato real — mismo mecanismo que el hallazgo de FINISH en
    `top_supervisor._make_supervisor_node`, acá a nivel del supervisor de
    dominio en vez del router raíz.
    """
    from langgraph_supervisor import create_supervisor

    workers = build_crypto_alt_workers()

    supervisor = create_supervisor(
        model=get_chat_model("supervisor"),
        agents=[
            workers["market_data_worker"],
            workers["alt_data_worker"],
        ],
        prompt=(
            "Sos el supervisor del equipo de Crypto & Alternative Assets de "
            "FinHive. Coordinás dos analistas: market_data_worker (precios y "
            "mercado de una cripto específica) y alt_data_worker (tendencias "
            "y ranking por market cap). Asigná cada parte de la pregunta al "
            "analista correspondiente, uno a la vez, y después sintetizá sus "
            "respuestas en un análisis coherente. No inventes datos vos "
            "mismo — todo dato numérico tiene que venir de un analista. Una "
            "vez que un analista ya te dio el dato pedido, respondé vos "
            "mismo con la síntesis final — no lo vuelvas a invocar pidiendo "
            "que confirme o repita. Ejemplo concreto: si preguntan el "
            "precio actual de Bitcoin y market_data_worker ya respondió "
            "'El precio actual de Bitcoin es $77641 USD', esa es la "
            "respuesta final — sintetizala y cerrá ahí, no le vuelvas a "
            "preguntar a market_data_worker ni cierres solo con '¿necesitás "
            "más información?' sin dar el dato. Este es un sistema de "
            "research, no de asesoramiento financiero: no des "
            "recomendaciones de compra/venta."
        ),
        add_handoff_back_messages=True,
        output_mode="full_history",
    )
    return supervisor.compile()

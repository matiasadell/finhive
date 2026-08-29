# ADR 0011 — Guardrails de entrada y salida como nodos propios del grafo

- **Estado**: aceptado
- **Fecha**: 2026-08-29

## Contexto

Dos de los bugs reales ya documentados en este proyecto son, en el fondo, el mismo
problema: el sistema devolvió un dato inventado en vez de admitir que no lo tenía.

- ADR 0004: `UCFunctionToolkit` en modo local falla silenciosamente en Windows
  (`import resource`, módulo Unix-only) → el worker de macro alucinó 5.25% de tasa de
  fondos federales; el valor real, verificado por separado, era 3.63%.
- ADR 0006: una pregunta de frontera ("¿cuándo es el próximo earnings de Apple?") se
  ruteó al equipo equivocado (`equity` en vez de `news_sentiment`) → sin la tool de
  calendario, `equity` inventó una fecha (2025 en vez de 2026).

Ninguno de los dos era un fallo de "falta de inteligencia" del modelo — eran fallos de
plataforma/routing que un LLM, por diseño, tapa con una respuesta plausible en vez de
fallar ruidosamente. Eso es exactamente lo que un guardrail de salida (fact-checking /
grounding rail) está pensado para atajar.

Además, hasta ahora cualquier pedido —tenga o no sentido para un sistema financiero—
llega directo al supervisor raíz y potencialmente gasta 1-3 vueltas de
supervisor→equipo→supervisor antes de que quede claro que no había nada que responder.
Un guardrail de entrada (moderation rail) corta eso antes de gastar esa cuota.

## Decisión

Guardrails implementados como **nodos propios de LangGraph**, no como una librería
dedicada (se evaluó NeMo Guardrails — ver `docs/latex/presentation.tex`, una
presentación previa no relacionada con FinHive que cubre ese framework en detalle). Se
descartó por la misma razón que ADR 0004 descartó los Managed MCP servers: una
dependencia externa con su propio DSL (Colang) agrega superficie de integración con un
supervisor jerárquico de LangGraph sin verificar, cuando el mismo resultado se logra con
dos nodos que usan el modelo worker (`get_chat_model("worker")`, Llama 3.1 8B, barato) y
`with_structured_output` — la misma herramienta que ya usa `_Router` en
`top_supervisor.py`.

Dos guardrails, ambos a nivel del top-level supervisor únicamente (no replicados dentro
de cada uno de los 5 sub-supervisores — ver "Alcance" en Consecuencias):

1. **`finhive.guardrails.input_guardrail.input_guardrail_node`** — primer nodo del
   grafo (`START -> input_guardrail`). Clasifica el pedido del usuario como
   `in_scope` (research financiero de alguno de los 5 dominios) o no (tema no
   financiero, intento de prompt injection, pedido de asesoramiento personalizado). Si
   no aplica, corta directo a `END` con un mensaje de rechazo — el supervisor raíz y los
   equipos de dominio ni se invocan.
2. **`finhive.guardrails.output_guardrail.output_guardrail_node`** — paso obligatorio
   antes de `END`, tanto si el supervisor decidió `FINISH` como si se cortó por
   `_MAX_ITERATIONS`. Recibe el historial completo (incluyendo los mensajes
   `<equipo>_team`, la única evidencia real disponible) y clasifica si la respuesta
   final está respaldada por esa evidencia. Si no, **no reintenta** — agrega un mensaje
   de advertencia explícito en vez de bloquear o corregir la respuesta, porque
   reintentar implicaría loopear de vuelta al supervisor con el consumo de cuota que
   eso trae, y el objetivo acá es visibilidad, no un segundo intento automático.

`_Router` en `top_supervisor.py` ya había resuelto el bug de `Literal[*options]` +
`with_structured_output` (ADR 0005) usando un campo `str` simple validado en código en
vez de un `Literal` construido en runtime — ambos guardrails reusan el mismo patrón
(`_TopicCheck.in_scope: str`, `_GroundednessCheck.grounded: str`) para no reintroducir
ese bug.

El flujo del grafo pasa de `START -> supervisor -> ... -> END` a `START ->
input_guardrail -> supervisor -> (equipos) -> supervisor -> ... -> output_guardrail ->
END`.

## Consecuencias

- **Costo/latencia**: cada conversación completa ahora paga 2 llamadas extra al modelo
  worker (input + output guardrail), sin importar cuántos equipos de dominio se
  invoquen — marginal comparado con las 2-6 llamadas que ya hacía el sistema por
  pregunta.
- **Alcance deliberadamente limitado**: los guardrails corren una vez, alrededor de
  *todo* el sistema, no dentro de cada uno de los 5 sub-supervisores. Es defensa en
  profundidad parcial, no completa — un dato inventado por un worker específico que el
  supervisor raíz sintetiza sin cambios sigue pasando por el mismo chequeo de
  groundedness al final, así que el caso real ya documentado (ADR 0004, ADR 0006) sigue
  cubierto; lo que no se cubre es un guardrail de entrada *por dominio* (ej. alguien le
  pregunta a `equity` directamente algo fuera de su scope sin pasar por el router raíz
  — no ocurre en el flujo normal, porque solo el top-level supervisor es el entry point
  público). Documentado como trabajo futuro si se decide exponer los sub-supervisores
  como entry points independientes.
- **Sin retry automático**: `output_guardrail` marca, no corrige. Un loop de
  autocorrección (reinyectar la advertencia al supervisor y pedirle que re-verifique con
  las tools) es la extensión natural, pero se dejó fuera de esta primera pasada para no
  sumar otra fuente de iteraciones sin límite además de `_MAX_ITERATIONS`.
- El campo `next` del state (`FinHiveState`) no cambió — los guardrails no lo tocan, solo
  agregan mensajes y deciden `goto`.
- Nuevo test: `tests/integration/test_guardrails.py` — un caso fuera de scope (verifica
  que ningún equipo de dominio se invoca) y un caso financiero real (verifica que pasa
  ambos guardrails y llega a delegar en un equipo).

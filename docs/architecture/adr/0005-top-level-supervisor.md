# ADR 0005 — Top-level supervisor: structured output y límite de iteraciones

- **Estado**: aceptado
- **Fecha**: 2026-08-29

## Contexto

Se implementó el supervisor raíz (`src/finhive/graph/top_supervisor.py`), que compone
sub-supervisores de dominio como subgrafos — patrón "Hierarchical Agent Teams" del
notebook de referencia. Con Macro como único equipo real, aparecieron dos problemas al
probar contra Databricks real, ninguno visible en la compilación del grafo (`.compile()`
no ejecuta nada, solo valida estructura).

## Problema 1 — `Literal[*options]` rompe `with_structured_output`

El notebook de referencia usa `Literal[*options]` (unpacking de una lista en runtime)
para el campo `next` de un `TypedDict` de routing. Con `ChatDatabricks.with_structured_output`,
esto crashea: `TypeError: issubclass() arg 1 must be a class`, dentro de la conversión a
schema de OpenAI functions (`_convert_pydantic_to_openai_function` → `model.schema()` vía
el shim de compatibilidad pydantic v1 de `langchain_core`). El `Literal` construido con
unpacking en runtime no es manejado correctamente por ese path.

**Decisión**: el campo `next` del `TypedDict` de routing es `str` simple, no `Literal`.
La validación de que el valor devuelto es uno de los equipos válidos (o `FINISH`) se hace
en código Python después de la llamada, con un fallback defensivo (al primer miembro) si
el LLM devuelve algo inesperado — más robusto que confiar en que el schema lo rechace.

## Problema 2 — el supervisor no paraba solo

Probado end-to-end, el supervisor raíz re-ruteó al equipo `macro` **9 veces** sobre una
pregunta que el equipo ya había respondido completamente en la primera vuelta, antes de
finalmente decidir `FINISH`. Cada vuelta de más es una llamada al supervisor (Llama 3.3
70B) más una invocación completa del sub-supervisor de Macro (varias llamadas internas
más) — esto fue, en la práctica, la causa más probable del `429 REQUEST_LIMIT_EXCEEDED`
(cuota de requests del Free Edition) que apareció durante las pruebas.

**Decisión**: dos mitigaciones combinadas, no una sola:
1. Prompt más explícito: "si el último mensaje de un equipo ya contesta la pregunta
   original, respondé FINISH inmediatamente — no vuelvas a consultar al mismo equipo
   sobre algo que ya respondió."
2. Un **límite duro de iteraciones** (`_MAX_ITERATIONS = 3`) en `FinHiveState.iterations`,
   incrementado en cada vuelta supervisor→equipo. Al alcanzarlo, se fuerza `FINISH` sin
   volver a preguntarle al LLM — no depende de que el modelo "se porte bien".

Con ambas mitigaciones, la misma clase de pregunta que antes tomaba 9 vueltas ahora
resuelve en 1.

## Consecuencias

- El límite de iteraciones es un patrón que **todo** grafo jerárquico de FinHive debería
  tener, no solo el top-level: al agregar guardrails más adelante, aplicar el mismo
  principio (cap duro, no solo instrucción de prompt) donde haya un loop supervisor↔worker.
- Confirma en la práctica algo ya anotado en ADR 0003: el `429` que aparece bajo carga es
  cuota, no facturación — el sistema se frena, no cobra. Pero cuota consumida
  innecesariamente por un loop mal acotado sigue siendo un desperdicio a evitar.
- Al sumar equity/portfolio_risk/news_sentiment/crypto_alt como equipos reales, este mismo
  supervisor debería seguir funcionando sin cambios — el prompt y el router ya generalizan
  sobre `members: list[str]`.

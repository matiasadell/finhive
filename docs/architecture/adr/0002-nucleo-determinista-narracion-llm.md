# ADR 0002 — Núcleo determinista, LLM solo para routing y narración

- **Estado**: aceptado
- **Fecha**: 2026-09-01

## Contexto

El challenge pide explicabilidad de las recomendaciones ("recommendation explainability"
es uno de los 4 criterios de evaluación) y esta máquina de desarrollo no tiene conexión a
Databricks (ver `prompts/constraints_environment.md`) — cualquier lógica que dependiera de
una llamada LLM real para producir un score, un match de duplicado, o un estado de value
realization no se podría verificar acá, solo en la compu de trabajo.

finhive (ADR 0004/0007 archivadas) ya estableció el principio de que las tools son la
fuente de verdad de los datos, no el LLM — pero seguía siendo el LLM el que interpretaba
esos datos crudos (precio de una acción, tasa de interés) para responder. Acá el dominio
es distinto: hay una decisión de negocio real (priorizar, consolidar, discontinuar) que
se puede calcular con una fórmula explícita sobre columnas del dataset, no solo consultar.

## Decisión

Toda decisión con impacto en la recomendación final la calcula una función Python pura en
`tools/` — nunca el LLM:

- `prioritization_tools.compute_priority_scores` — composite score con pesos documentados.
- `duplication_tools.find_duplicate_use_cases` — similitud textual (Jaccard) + metadata
  compartida, sin LLM ni embeddings.
- `value_realization_tools.compute_value_realization_status` — 3 señales binarias
  (cost_overrun, timeline_breach, documented_barrier) sobre columnas reales.
- `recommendation_tools.generate_portfolio_recommendations` — tabla de reglas explícita
  sobre las tres anteriores.

Los 4 agentes ReAct (`agents/*.py`) solo pueden invocar estas tools y narrar sus
resultados en lenguaje natural — el system prompt de cada uno lo dice explícito ("nunca
inventes/recalcules un número vos mismo"), y `guardrails/output_guardrail.py` verifica
groundedness contra la evidencia real de las tools antes de devolver la respuesta final.

## Consecuencias

- **La mitad del sistema es verificable sin LLM, en esta máquina de desarrollo.** Todo lo
  que respalda "prioritization quality", "reuse identification" y "value realization"
  (3 de los 4 criterios del challenge) es una función pura, testeada en `tests/unit/`
  (29 tests) y validada contra el golden set completo (`data/eval/golden_set.json`, 11/11
  checks) sin ninguna conexión a Databricks. Solo el routing entre agentes y la narración
  final necesitan el LLM real — eso se prueba recién en la compu de trabajo
  (`tests/integration/test_live_agents.py`, marcado `live`).
- El reporte ejecutivo (`reporting/executive_report.py`, deliverable de "executive
  recommendation output" del challenge) se genera directo del pipeline de tools, sin pasar
  por el grafo de agentes — es 100% reproducible y auditable línea por línea contra el
  dataset fuente.
- Costo: los agentes son menos "flexibles" que un LLM libre para responder preguntas fuera
  del vocabulario de las tools -- una pregunta genuinamente nueva que no calce con ningún
  tool existente no tiene forma de responderse bien. Se acepta ese costo a cambio de la
  explicabilidad y la testeabilidad local.

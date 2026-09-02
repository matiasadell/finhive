# ADR 0004 — Sin memoria persistente, RAG ni despliegue como Agent (en este pase)

- **Estado**: aceptado
- **Fecha**: 2026-09-01

## Contexto

finhive tiene memoria de sesión + hechos de largo plazo (`memory/`, ADR 0012 archivada),
RAG sobre filings vía Vector Search (`rag/`, ADR 0017 archivada), y un wrapper
`ResponsesAgent` para desplegarse como Agent de Databricks (`serving/`, ADR 0015
archivada). Los tres son piezas reales y probadas, pero el usuario confirmó explícitamente
que ninguna aplica a este proyecto en este pase (ver `prompts/non_goals.md`): sin memoria
conversacional (cada corrida analiza el portfolio actual desde cero), sin ingesta de
documentos narrativos (el dataset es tabular, no hay filings que indexar), y sin
servidor/deployment (el equipo del usuario construye su propio frontend, ver
`prompts/constraints_tech_stack.md`).

## Decisión

`src/finhive/{memory,rag,serving}/` se eliminaron al hacer `git mv src/finhive
src/portfolio_intel` (Task 1) — no se adaptaron ni se dejaron como código muerto. El grafo
de Portfolio Intel (`graph/top_supervisor.py`) es explícitamente más simple que el de
finhive: `START → input_guardrail → supervisor → (agentes) → ... → output_guardrail →
END`, sin los nodos `memory_recall`/`memory_remember` que sí tiene finhive.

## Consecuencias

- Menos superficie de código para un desarrollo de 1-3 días — más tiempo en el núcleo
  determinista (ADR 0002), que es lo que de verdad se evalúa (prioritization quality,
  reuse identification, value realization, explainability).
- Si el proyecto sigue más adelante y se vuelve conversacional de verdad (un
  chat multi-turno con el portfolio), el patrón de `memory/` de finhive es directamente
  reusable — mismo criterio de tablas Delta en Unity Catalog, mismo diseño de
  `memory_recall`/`memory_remember` como nodos del grafo, no como tools invocadas por el LLM.
- Sin RAG: si en algún momento el dataset incluyera texto narrativo largo (ej. actas de
  comités de aprobación, documentos de business case completos en vez de un campo
  `business challenge` de una oración), el patrón de `rag/ingest.py` + Vector Search de
  finhive sería el punto de partida, no algo a diseñar de cero.

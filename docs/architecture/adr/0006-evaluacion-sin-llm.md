# ADR 0006 — Evaluación formal sin LLM-judge, contra el núcleo determinista

- **Estado**: aceptado
- **Fecha**: 2026-09-01

## Contexto

finhive evalúa el sistema completo con `mlflow.genai.evaluate()` contra Databricks real,
incluido un LLM-judge de groundedness (ADR 0013/0014 archivadas) — no reproducible acá,
sin conexión a Databricks. El usuario pidió igual evaluación formal ("technical
effectiveness measured by relevant metrics" es parte de la rúbrica del hackathon), así que
hacía falta un diseño que diera una métrica real y verificable en esta máquina.

## Decisión

`data/eval/golden_set.json` tiene 11 escenarios, cada uno nombrando un `use case id`
concreto del dataset sintético (ver `data/sample_docs/README.md`) y la señal determinista
esperada: un par duplicado, presencia en el top-N de prioridad, un `value_status`
esperado, o una acción de recomendación esperada. `evaluation/metrics.py` corre el
pipeline de `tools/` **una sola vez** (`EvalContext.build`) y evalúa los 4 tipos de check
contra ese resultado — sin ningún LLM involucrado, a propósito (ver ADR 0002).

`evaluation/run_eval.py` corre esto y, además, intenta loguear a MLflow de forma
*best-effort*: si no hay conexión a Databricks (el caso normal acá), se explica por
consola y se sigue — mismo patrón "falla fuerte pero no bloquea" del resto del proyecto
(ver `prompts/constraints_environment.md`).

## Consecuencias

- `python -m portfolio_intel.evaluation.run_eval` da un pass rate real (11/11, 100%) en
  esta máquina de desarrollo, sin depender de nada externo — a diferencia de la
  evaluación de finhive, que solo corre en la compu de trabajo.
- Esta evaluación mide la calidad del *núcleo determinista* (¿el scoring, la detección de
  duplicados, el value_status, y las reglas de recomendación están bien calibrados contra
  los escenarios que el dataset construye a propósito?) — no mide la calidad del routing
  ni de la narración del LLM, que son las dos piezas que sí necesitan el sistema completo
  corriendo en Databricks para evaluarse (ver `tests/integration/test_live_agents.py`).
  Ambas evaluaciones son complementarias, no sustitutas una de la otra.
- Si un check del golden set falla, es señal de un bug real en `tools/` o de una
  expectativa mal calibrada en el dataset sintético (ver ADR 0005) -- nunca de un flake de
  LLM, porque no hay LLM en el camino.

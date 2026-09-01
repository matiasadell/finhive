# ADR 0014 — Reemplazo de LangSmith por evaluación nativa de MLflow GenAI

- **Estado**: aceptado
- **Fecha**: 2026-08-30
- **Supersede**: ADR 0001 (fila 6, "Observabilidad"), ADR 0013 (mecanismo de ejecución de la evaluación formal — el diseño y los 5 bugs documentados ahí siguen siendo la referencia histórica)

## Contexto

ADR 0001 registró la decisión original de usar LangSmith y MLflow en paralelo para
observabilidad/evaluación — deliberada desde el arranque del proyecto: *"el usuario
quiso ambos explícitamente, para comparar los dos enfoques"*. ADR 0013 construyó la
evaluación formal sobre `langsmith.evaluate()`, con MLflow como punto de agregación
del resumen dentro de Databricks.

Con MLflow 3, la UI de un Experiment en Databricks pasó a tener secciones nativas de
GenAI (Observability: Traces, Sessions; Evaluation: Scorers, Datasets, Evaluation
runs, Labeling; Prompts & versions) que cubren lo mismo que se comparaba contra
LangSmith. El usuario decidió consolidar todo en Databricks y sacar LangSmith del
proyecto por completo — un dependency, una API key y un sistema externo menos.

Antes de migrar se verificó explícitamente que `mlflow.genai.evaluate()` no tuviera
la misma limitación con la que se chocó en la misma sesión al intentar mandar las
trazas del notebook de demo a Unity Catalog (`MlflowException: ... Tables created in
default storage are not supported` — Free Edition solo tiene catalogs de storage
default, sin cuenta de cloud propia detrás). Confirmado en la documentación oficial:
`evaluate()` acepta una lista simple de dicts como dataset y no requiere ninguna
tabla de Unity Catalog ni SQL warehouse para correr — sin ese riesgo, se decidió
seguir adelante.

## Decisión

Se migra `src/finhive/evaluation/run_eval.py` y `metrics.py` de `langsmith.evaluate()`
a `mlflow.genai.evaluate()`:

- Los tres evaluadores (`routing_accuracy`, `latency`, `groundedness`) pasan a ser
  funciones `@scorer` de `mlflow.genai.scorers`, con la firma keyword-only de MLflow
  (`inputs`/`outputs`/`expectations` en vez de `run`/`example` de LangSmith) — **la
  lógica interna no cambia**, incluido el prompt propio de `groundedness` sobre
  `get_chat_model("supervisor")` (validado en ADR 0011/0013). No se adopta el judge
  built-in `RetrievalGroundedness` de MLflow: no había necesidad de re-validar
  comportamiento/costo/disponibilidad de un judge nuevo cuando el propio ya está
  probado.
- `data/eval/golden_set.json` se pasa directo como `data=[{"inputs": {"question":
  ...}, "expectations": {"expected_teams": ...}}, ...]` a `evaluate()` — ya no hace
  falta el paso de registrar el dataset en un sistema aparte (`Client.create_dataset`
  + `create_examples` de LangSmith desaparece entero).
- `predict_fn(question: str) -> dict` reemplaza a `target(inputs)`, misma lógica
  (`graph.invoke()` con `thread_id` nuevo por pregunta, ADR 0013).
- El workaround de `_log_results_table` (ADR 0013, hallazgo #1: `mlflow.log_table`
  rompía con `ujson` sobre texto real del dataset) se elimina — la UI nativa de
  Evaluation runs guarda el detalle por pregunta (`results.tables["eval_results"]`)
  sin ese paso manual.
- `mlflow.genai.evaluate()` corre `predict_fn` con **10 preguntas en paralelo por
  default** (`MLFLOW_GENAI_EVAL_MAX_WORKERS`, env var no documentada en la firma de
  la función ni en su docstring — solo aparece en el código fuente del harness). Se
  fija en `1` con `os.environ.setdefault(...)` antes de correr `evaluate()`, mismo
  mecanismo y misma razón que el `max_concurrency=1` que ya hacía falta con
  `langsmith.evaluate()` (ADR 0013): 10 preguntas concurrentes × ~4 llamadas LLM cada
  una saturan el rate limit de 30 llamadas/usuario/min del tier supervisor (ADR 0008)
  más rápido de lo que el rate-limiter adaptativo interno de MLflow puede compensar —
  ver hallazgo #1 más abajo.

`pyproject.toml`: se saca `langsmith>=0.1`; `mlflow>=2.16` sube a
`mlflow[databricks]>=3.1.0` (mínimo real de la API de evaluación GenAI). `.env.example`
pierde `LANGSMITH_API_KEY`/`LANGSMITH_PROJECT`/`LANGSMITH_TRACING`.

## El bug real encontrado en el proceso

Primera corrida completa del dataset dorado (15 preguntas) con el harness nuevo, sin
fijar `MLFLOW_GENAI_EVAL_MAX_WORKERS`: terminó en 3:34 (contra los ~10 min esperados),
con `routing_accuracy=0.267` y `groundedness` calculado sobre solo 2 de 13 preguntas
de dominio — números que no cuadraban con nada de lo verificado manualmente en toda
la sesión. Diagnosticado consultando las trazas de esa corrida directo por
`mlflow.search_traces()` (mismo mecanismo que ya se usó antes en esta sesión para leer
trazas del notebook de demo sin Unity Catalog): de 15 preguntas, había **20 trazas**
(reintentos) y **solo una con `response` real** — el resto, `response: None`.
`predict_fn` estaba tirando una excepción de rate-limit sin atrapar en casi todas las
preguntas (no cubierta por `safe_tool`, que solo envuelve tools de datos, no llamadas
al LLM). Causa raíz encontrada leyendo el código fuente de
`mlflow.genai.evaluation.base` (no está en la documentación pública ni en el
docstring de `evaluate()`): `MLFLOW_GENAI_EVAL_MAX_WORKERS` default **10** — 10
preguntas concurrentes, cada una disparando varias llamadas al tier supervisor,
agotan el rate limit de ADR 0008 antes de que el rate-limiter adaptativo de MLflow
llegue a compensarlo. Fix: `os.environ.setdefault("MLFLOW_GENAI_EVAL_MAX_WORKERS", "1")`
al principio de `run_eval.py`. Con eso, la corrida completa volvió a los ~12 minutos
esperables y a números coherentes con el resto de la sesión.

## Verificación

Corrida en vivo contra Databricks real, dataset dorado completo (15 preguntas), con
el fix de concurrencia ya aplicado:

| Métrica | Valor |
|---|---|
| `routing_accuracy` | **0.933** (14/15) |
| `groundedness` | **0.917** (sobre 12 preguntas de dominio evaluadas) |
| latencia promedio | **33.65s/pregunta** |

Resultado logueado en el mismo Experiment de MLflow que ya usaba ADR 0013
(`/Users/<usuario>/finhive-eval`), visible en la pestaña Evaluation runs. Números
distintos a los de ADR 0013 (routing 1.0, groundedness 0.846) — esperable: el prompt
del router cambió en el medio (ver el fix de FINISH de esta misma sesión) y hay
variación normal de corrida a corrida por no-determinismo del LLM, ya documentada
como comportamiento esperado en ADR 0013.

## Consecuencias

- Un dependency, una API key y un sistema externo menos — todo el ciclo de
  observabilidad/evaluación vive en Databricks.
- Se pierde la comparación entre corridas de LangSmith en su propia UI (su punto
  fuerte real) — trade-off aceptado a cambio de consolidación; MLflow también
  versiona corridas de evaluación (Evaluation runs por Experiment), aunque con una
  UI distinta.
- `langsmith` puede seguir instalado de forma transitiva (es dependencia base de
  `langchain-core`) aunque ya no esté en `pyproject.toml` como dependencia directa —
  esperado, no rompe nada: sin `LANGSMITH_API_KEY`/`LANGSMITH_TRACING` seteadas, su
  integración de tracing automático simplemente no se activa.
- ADR 0001 y ADR 0013 se mantienen sin editar como registro histórico de la decisión
  original y del diseño que encontró los 5 bugs reales — mismo criterio que ya usa
  ADR 0003 al supersede ADR 0002 sin borrarlo.
- `docs/architecture/adr/0006-routing-entre-dominios.md` y `notebooks/README.md`
  tenían menciones de LangSmith en referencias a trabajo futuro — actualizadas para
  no quedar desactualizadas, sin ser parte central de esta decisión.

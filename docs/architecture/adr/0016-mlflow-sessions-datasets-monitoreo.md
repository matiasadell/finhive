# ADR 0016 — Sessions, Evaluation Datasets en UC y monitoreo de producción

- **Estado**: aceptado
- **Fecha**: 2026-08-31

## Contexto

Revisando la UI de un Experiment de MLflow 3 en Databricks (Observability,
Evaluation, Prompts & versions), quedó claro que FinHive usaba solo dos
secciones (Traces, Evaluation runs) de un conjunto bastante más amplio.
Se evaluaron las 5 piezas no usadas y se decidió cuáles valían la pena para
un proyecto personal:

- **Sessions**, **monitoreo de producción** y **Evaluation Datasets en UC**:
  adoptados (esta ADR).
- **Prompt Registry**: descartado por ahora — su valor fuerte es para
  equipos con gente no técnica editando prompts sin deploy; acá git ya
  versiona cada prompt con mensajes de commit ricos en contexto, y varias
  ADRs (0014, 0015) ya documentan el *por qué* de cada cambio de prompt con
  más detalle del que daría un mensaje de commit de prompt registry.
- **Labeling sessions/schemas + Review App**: no descartado, pero fuera de
  esta ADR — su caso de uso principal (dominio experts revisando trazas en
  equipo) no aplica a un proyecto de un solo usuario; la Review App que ya
  se creó al desplegar el Agent (ADR 0015) queda disponible para uso
  informal si hace falta más adelante.

## Decisión 1: Sessions vía `mlflow.update_current_trace(session_id=...)`

`memory_recall_node` (`src/finhive/memory/nodes.py`) ya calcula `thread_id`
al principio de cada invocación del grafo completo — el mismo identificador
que usa la memoria de sesión real (ADR 0012). Se agrega
`mlflow.update_current_trace(session_id=thread_id)` ahí mismo: las trazas
quedan agrupadas por conversación en Observability > Sessions sin mantener
una noción de sesión aparte. Sin traza activa (ej. un test que llama al nodo
directo) la función solo loguea un warning, no rompe nada — confirmado
leyendo el código fuente de MLflow antes de aplicar el cambio.

Verificado en vivo: una traza real quedó con
`mlflow.trace.session = <thread_id real>` en su metadata.

## Decisión 2: `golden_set.json` sincronizado a un `EvaluationDataset` en UC

`data/eval/golden_set.json` sigue siendo la fuente de verdad única
versionada en git (mismo criterio que ADR 0013/0014) — se agrega
`sync_uc_dataset()` en `golden_set.py`, que sincroniza (no reemplaza) una
copia hacia `workspace.finhive.golden_set`, un `EvaluationDataset` real de
MLflow en Unity Catalog. `run_eval.py` ahora pasa ese dataset (no una lista
de dicts suelta) a `mlflow.genai.evaluate()`, ganando versionado y lineage
(qué corrida de evaluación usó qué versión del dataset) sin costo real
adicional — `merge_records()` es idempotente (un registro con el mismo
`inputs` actualiza en vez de duplicar), así que sincronizar en cada corrida
no acumula basura.

Hallazgo real en el camino: `get_dataset()` no envuelve el "no existe" en un
`MlflowException` como se esperaba — deja pasar
`databricks.sdk.errors.NotFound` directo, sin documentar. Se atrapan ambas
excepciones en vez de una sola, para no depender de un detalle interno que
podría cambiar.

Verificado en vivo: dataset creado con las 15 preguntas, idempotente en una
segunda corrida (15 registros, no 30), y la evaluación completa corrida a
través de él end-to-end (routing accuracy 0.933, groundedness 1.000,
latencia 32.94s).

## Decisión 3: monitoreo de producción con un scorer `Guidelines`

El Agent desplegado (ADR 0015) ya genera trazas reales en el experimento
`finhive-agent-deploy`. Nuevo script `infra/databricks/setup_production_monitoring.py`
registra y activa un scorer built-in `Guidelines` ("no dar recomendaciones
de inversión personalizadas" — la misma restricción que ya está en los 6
prompts del grafo) con `sample_rate=0.3` sobre ese experimento: cierra el
loop entre "lo evaluamos offline contra 15 preguntas fijas" (`run_eval.py`)
y "¿sigue siendo bueno con preguntas reales que el dataset dorado nunca
vio?". Usa el judge nativo de Databricks (`model="databricks"`) en vez del
`get_chat_model("supervisor")` propio que ya usan los guardrails y el
scorer de groundedness — es el default recomendado por Databricks para
scorers built-in, no se reemplazó por costo/disponibilidad sin verificar
(primer lugar donde mirar si el monitoreo no aporta datos con el tiempo).

Verificado en vivo: `list_scorers()` muestra `no_investment_advice` con
`status=STARTED` y `sample_rate=0.3` sobre el experimento correcto.

## Consecuencias

- No se tocó `notebooks/01_deploy_agent.py` ni se volvió a desplegar el
  Agent para este cambio — el fix de Sessions (memory/nodes.py) ya viaja
  con el paquete `finhive`, pero el endpoint desplegado sigue sirviendo la
  versión logueada antes de este cambio hasta el próximo redeploy real. No
  se justificó gastar cuota de Model Serving (ADR 0015, hallazgo #7) solo
  por esto.
- El scorer de monitoreo de producción es un gasto real y continuo de
  llamadas al judge nativo de Databricks (30% del tráfico) — aceptable en
  Free Edition mientras el volumen de uso siga siendo personal/bajo, primer
  lugar donde bajar el `sample_rate` si eso cambia.
- `workspace.finhive.golden_set` es una tabla más en el mismo schema que ya
  usan la memoria persistente (ADR 0012) y el modelo registrado (ADR 0015) —
  sin permisos adicionales que gestionar.

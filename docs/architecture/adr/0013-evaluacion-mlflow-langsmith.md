# ADR 0013 — Evaluación formal: dataset dorado, LangSmith `evaluate()`, resumen en MLflow

- **Estado**: aceptado
- **Fecha**: 2026-08-29

## Contexto

Hasta ahora, "calidad" en FinHive se medía de dos formas indirectas: tracing (MLflow
autolog / LangSmith automático, vía las env vars `LANGSMITH_*` ya en `.env`) para
inspeccionar una corrida puntual, y el guardrail de salida (ADR 0011) como gate
pass/fail sobre una sola conversación a la vez. Ninguna de las dos cosas es una
**evaluación formal**: un conjunto fijo de preguntas, corridas de punta a punta,
puntuadas con métricas explícitas y comparables entre corridas.

Esta pieza terminó siendo la que más bugs reales encontró de todo el proyecto — no
porque el código estuviera particularmente mal, sino porque es la primera vez que se
corrió el sistema contra un conjunto amplio y variado de preguntas de una sola vez, en
vez de una o dos por sesión de trabajo manual. Quedan documentados los cinco hallazgos
en el orden en que aparecieron, cada uno verificado en vivo antes y después del fix.

## Decisión: diseño de la evaluación

### Dataset dorado versionado en el repo, no autorado en la UI de LangSmith

`data/eval/golden_set.json` — 15 preguntas: 2 por cada uno de los 5 dominios, 2
cross-domain, 2 fuera de scope (una simplemente no financiera, otra un intento de
prompt injection), y **1 caso límite real**: "¿cuándo es el próximo earnings de Apple?"
— exactamente la pregunta que causó el bug de ruteo documentado en ADR 0006. Es un test
de regresión real, no una pregunta inventada. Fuente de verdad única y versionada; se
sube desde ahí tanto a LangSmith (`Client.create_dataset` + `create_examples`, una vez,
idempotente vía `has_dataset`) como a MLflow (como tabla de resultados).

### `langsmith.evaluate()` como motor único de ejecución

`finhive.evaluation.run_eval.target(inputs) -> dict` invoca
`build_top_supervisor().invoke(...)` con un `thread_id` nuevo por pregunta y devuelve
`answer`, `actual_teams`, `blocked`, `latency_seconds` y `team_evidence`. El grafo corre
una única vez por pregunta — los mismos resultados que produce `evaluate()` son los que
se resumen y suben a MLflow después, no una segunda corrida. `max_concurrency=1`: el
tier supervisor del AI Gateway tiene rate limit de 30 llamadas/usuario/min (ADR 0008).

### Tres métricas (`finhive/evaluation/metrics.py`)

- **`routing_accuracy`** — determinista. Un solo dominio: coincidencia exacta. Cross-domain:
  alcanza con que todos los equipos esperados hayan sido tocados. Fuera de scope:
  correcto si `input_guardrail` bloqueó sin invocar ningún equipo.
- **`latency_seconds`** — determinista, `time.perf_counter()` alrededor de todo
  `graph.invoke()` (guardrails + memoria + supervisor + equipos incluidos).
- **`groundedness`** — LLM-judge, mismo patrón `_GroundednessCheck` del guardrail de
  salida (ADR 0011). No aplica a preguntas bloqueadas (`score=None`, no `0.0`).

## Los cinco hallazgos reales, en orden

### 1. `mlflow.log_table` rompe con texto real (`OverflowError: Unterminated UTF-8 sequence`)

La primera corrida completa terminó con esa excepción justo al loguear la tabla de
resultados — después de que las 15 preguntas ya habían corrido bien. El backend `ujson`
de pandas no tolera algún carácter mal formado en el texto real (probable objeto anidado
que `to_pandas()` de LangSmith deja en una columna de feedback, no necesariamente un
`str` plano — una limpieza célula por célula con `.encode('utf-8', errors='replace')`
**no alcanzó** a evitarlo, se probó primero y falló igual). Fix real: no usar
`mlflow.log_table` — serializar con `json.dumps(default=str, ensure_ascii=True)` (ASCII
puro, cualquier objeto no serializable cae a `str()`) y loguear el archivo con
`mlflow.log_artifact`. Verificado con un caso sintético (objeto anidado con un
surrogate suelto embebido) antes de volver a correr las 15 preguntas reales.

### 2. `output_guardrail` reemplazaba la respuesta real por el disclaimer

Con la groundedness real funcionando, apareció un patrón raro: varias respuestas
finales eran *solo* el texto de advertencia del guardrail de salida ("⚠️ Nota de
verificación automática..."), sin ningún dato. Causa: `output_guardrail_node` agregaba
el warning como un mensaje **nuevo**, dejándolo como el último mensaje del state — y
tanto `finhive.evaluation.run_eval.target()` como los tests de integración existentes
leen `messages[-1]` como "la respuesta". El dato real (con evidencia legítima de las
tools) seguía en el mensaje anterior, pero invisible para cualquier consumidor que solo
lea el último mensaje — que es el patrón más común. Fix: anteponer la respuesta original
al warning en el **mismo** mensaje, no agregarlo aparte (`output_guardrail.py`).

### 3. El modelo worker (Llama 3.1 8B) no es confiable como LLM-judge

Incluso después del fix #2, `groundedness` daba **0.0 en las 13 preguntas de dominio**
— sospechosamente uniforme para un juicio semántico real. Se aisló el problema
invocando el judge directo: con evidencia y respuesta *idénticas palabra por palabra*
("El precio actual de Bitcoin es $78,206 USD" en ambas), el modelo worker respondió
`grounded='no'` con una razón fabricada. El mismo prompt, mismo caso, con el modelo
`"supervisor"` (Llama 3.3 70B): `grounded='si'`, razón coherente. No era un problema de
prompt (se probó primero una aclaración explícita sobre "falta de detalle no es
alucinación" — no cambió nada) — el modelo de 8B genuinamente no es confiable para este
tipo de juicio. Fix: `groundedness_evaluator` (acá) y `output_guardrail_node` (ADR 0011,
corregido retroactivamente) pasan a usar `"supervisor"`. En Free Edition ambos tiers son
gratis — el único costo real es latencia, no dinero.

### 4. Orden del pipeline: `input_guardrail` antes de `memory_recall` rompía follow-ups

Corriendo `tests/integration/test_memory.py` con el pipeline ya así, una pregunta de
seguimiento legítima ("¿y cómo se compara ese precio con el de hace un mes?") a veces se
bloqueaba como fuera de scope. Causa raíz: `input_guardrail` corría *antes* que
`memory_recall` (orden original de ADR 0012) — sin el historial ya antepuesto, un
clasificador evaluando esa pregunta aislada razonablemente la marca `in_scope='no'`
(ninguna palabra financiera propia). Fix: reordenar el grafo a `START -> memory_recall ->
input_guardrail -> supervisor -> ...` — el guardrail de entrada ahora recibe el contexto
recuperado y clasifica con eso a la vista. Documentado explícitamente en
`input_guardrail.py`: un follow-up sobre la charla en sí (ej. "¿hace cuánto lo
preguntamos?") sigue rechazado con razón, sea cual sea el contexto — no es lo mismo que
un follow-up financiero que necesita contexto para tener sentido.

### 5. El mismo problema del hallazgo #3, en `input_guardrail`

Con el reordenamiento del #4 aplicado, la misma pregunta de seguimiento financiera
seguía fallando de forma intermitente entre una corrida y otra del mismo test —
corriendo el mismo código standalone, a veces pasaba. Mismo patrón que el hallazgo #3:
el clasificador de tópico también corre en el modelo worker, y no es perfectamente
determinista ni a `temperature=0` en un modelo de 8B servido. Acá el costo de un falso
rechazo es alto (una pregunta financiera legítima bloqueada), así que se aplicó el mismo
fix: `input_guardrail_node` pasa a usar `"supervisor"`. Verificado con 3 corridas
consecutivas del test después del cambio, todas en verde.

## Resultado final (verificado en vivo, con todos los fixes aplicados)

| Métrica | Valor |
|---|---|
| `routing_accuracy` | **1.0** (15/15 — incluye el caso límite de ADR 0006 y los 2 casos fuera de scope) |
| `groundedness` | **0.846** (11/13 preguntas de dominio; 2 excluidas del promedio por estar bloqueadas) |
| `avg_latency_seconds` | **38.4s** por pregunta (pipeline completo: guardrails + memoria + supervisor + equipo) |

Experiment de LangSmith y Run de MLflow (con `eval_results.json` como artifact) enlazados
entre sí — la URL de LangSmith queda logueada como parámetro del Run de MLflow.

## Consecuencias

- **Costo real de correr esto**: ~40s/pregunta × 15 preguntas con `max_concurrency=1` ≈
  10 minutos por corrida completa, más el cold-start del warehouse si estuvo inactivo.
  No corre en cada commit, a mano cuando hace falta re-evaluar.
- Tres nodos del sistema ahora usan el tier `"supervisor"` para juicios semánticos en vez
  de `"worker"`: el router (ya así desde ADR 0009/0010), `output_guardrail`, e
  `input_guardrail`. Los únicos nodos que siguen en `"worker"` son los deterministas de
  tool-calling (los 13 workers ReAct) y la extracción de hechos de largo plazo
  (`remember_fact_if_worth_it`, ADR 0012) — sin evidencia todavía de que esa necesite el
  modelo grande, pero es la primera candidata a revisar si aparece un patrón similar.
- `groundedness` en 0.846, no 1.0, es un resultado real y esperable — dos preguntas de
  dominio (sobre las 13 evaluadas) fueron marcadas como no completamente respaldadas por
  el judge de 70B; no se investigó cada una individualmente para esta ADR, es trabajo
  futuro natural si se quiere subir ese número.
- El dataset de LangSmith se crea una única vez (`has_dataset` lo hace idempotente); si
  `data/eval/golden_set.json` cambia, hay que borrar el dataset a mano o extender
  `_ensure_dataset` para sincronizar diffs — no implementado.
- Efecto colateral del hallazgo #4: `memory_recall` ahora corre para *toda* invocación,
  incluida una que termine bloqueada por `input_guardrail` — 2 lecturas SQL extra en el
  camino de rechazo que antes no existían. Costo aceptable (correctness por sobre unos
  milisegundos), documentado acá para que no sorprenda en un futuro perfil de latencia.
- Efecto colateral del hallazgo #4, en los tests: `tests/integration/test_guardrails.py`
  y `test_top_supervisor.py` no pasaban `thread_id` explícito, así que todos compartían
  el thread `"default"` — con memoria de sesión real, eso significa que corridas de test
  sucesivas se contaminan entre sí (mensajes de equipo de un test apareciendo en el
  resultado de otro). Corregido: ambos archivos ahora usan un `thread_id` único por
  test (`uuid.uuid4()`), mismo patrón que ya usaba `test_memory.py` correctamente.

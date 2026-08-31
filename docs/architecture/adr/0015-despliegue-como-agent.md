# ADR 0015 — Despliegue de FinHive como Agent (Mosaic AI Agent Framework)

- **Estado**: aceptado
- **Fecha**: 2026-08-31

## Contexto

Objetivo pendiente desde el arranque del proyecto (ver roadmap del README): que
FinHive aparezca en la pestaña **Agents** de Databricks, para poder mostrar el
repo como portfolio (ej. LinkedIn) con el sistema corriendo de verdad, no solo
como código. Requisito explícito del usuario: el repo puede ser público, pero
**nadie más que él** tiene que poder invocar el endpoint real.

Verificado antes de empezar (research + inspección del workspace):
- Free Edition permite Model Serving custom, no solo Foundation Model APIs —
  pero con cuota propia: si se excede, Databricks puede apagar **todo el
  workspace** por el resto del día/mes (distinto del comportamiento de los
  Foundation Model APIs, ADR 0003, donde pasarse de cuota solo bloquea la
  request). Se revisaron cuotas actuales antes de desplegar (11 endpoints
  activos, todos Foundation Model APIs nativos, cero endpoints custom previos).
- Nada en Databricks (Model Serving, Review App, Databricks Apps) es público por
  default — todo requiere autenticación de la cuenta y permisos explícitos. No
  se otorgó ningún grant adicional sobre el modelo registrado ni el endpoint
  (`CAN_QUERY` queda solo para el creador, el default) — eso solo ya satisface
  "nadie más lo puede usar".

## Decisión: `ResponsesAgent`, no `ChatAgent`

Databricks recomienda hoy `mlflow.pyfunc.ResponsesAgent` por sobre `ChatAgent`
para envolver agentes de frameworks de terceros. Se usa el patrón "models from
code" (`mlflow.pyfunc.log_model(python_model="chat_agent.py", ...)`, el archivo
llama a `mlflow.models.set_model(...)` al final) en vez de intentar loguear el
`CompiledStateGraph` de LangGraph directo con el flavor `langchain` de MLflow —
bug conocido, esa clase no está soportada por ese flavor.

`src/finhive/serving/chat_agent.py` no reimplementa nada: `FinHiveAgent.predict()`
llama a `build_top_supervisor()` tal cual, mismo grafo que usa el notebook de
demo y `run_eval.py` — guardrails, memoria (ADR 0012) y routing entre los 5
dominios sin cambios. `thread_id` es opcional vía `custom_inputs`: si el caller
lo manda, la conversación aprovecha memoria de sesión real entre llamadas al
endpoint; si no, cada invocación es independiente.

`infra/databricks/deploy_agent.py` (mismo patrón standalone que
`register_uc_functions.py`): loguea el modelo con `resources=` declarados
(`DatabricksServingEndpoint` para los dos endpoints de Foundation Model APIs y
para el model-service del router de AI Gateway, `DatabricksSQLWarehouse` para
la memoria), lo registra en Unity Catalog, y llama a `agents.deploy(...)` con
`scale_to_zero=True` y `workload_size="Small"` — uso personal de bajo volumen,
no una demo pública con tráfico real, minimiza cómputo activo contra la cuota.
Los secrets externos (FRED, Alpha Vantage, Tavily) se pasan al endpoint vía
`environment_vars` con sintaxis `{{secrets/finhive/...}}` — nunca en texto
plano, mismo scope `finhive` que ya usa el notebook de demo.

## El bug real encontrado en el proceso

Probando el flujo completo antes de desplegar, con la pregunta "¿cuál es el
precio actual de Bitcoin?": el sub-supervisor de `crypto_alt` (construido con
`langgraph_supervisor.create_supervisor`, ADR 0001/patrón "Multi Agent
Supervisor") volvió a invocar a `market_data_worker` después de que ya había
dado el precio real, y cerró con *"¿Necesitás más información sobre Bitcoin o
alguna otra criptomoneda?"* — sin el dato. Mismo mecanismo exacto que el
hallazgo de FINISH en `top_supervisor._make_supervisor_node` (esta misma
sesión, ver commit del fix del router raíz), pero a nivel de un supervisor de
**dominio**, no del router raíz — el fix original solo tocó `top_supervisor.py`.

Se aplicó el mismo patrón (instrucción explícita + ejemplo concreto en el
prompt, con el propio dato real de Bitcoin como ejemplo) a los 5
sub-supervisores de dominio (`macro`, `equity`, `portfolio_risk`,
`news_sentiment`, `crypto_alt`). Verificado en vivo: 5/5 respuestas correctas
repitiendo la pregunta de Bitcoin con un `thread_id` nuevo cada vez (antes:
fallaba de forma intermitente).

## Consecuencias

- El repo puede mostrarse públicamente sin exponer un endpoint utilizable por
  terceros — la privacidad viene gratis del modelo de permisos de Databricks,
  no de ningún mecanismo agregado ad-hoc.
- `scale_to_zero=True` significa que la primera invocación después de un rato
  de inactividad puede tardar en "despertar" el endpoint — aceptable para uso
  personal, no para una demo en vivo con público esperando respuesta instantánea.
- El fix de FINISH en los sub-supervisores de dominio es una mejora de calidad
  real independiente del deploy en sí — se aplicó acá porque se encontró
  probando el flujo de deploy, pero mejora también el notebook de demo y la
  evaluación formal (ADR 0014) por igual.

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
  activos, todos Foundation Model APIs nativos, cero endpoints custom previos)
  — y, como se documenta más abajo, se terminó chocando contra esa cuota igual.
- Nada en Databricks (Model Serving, Review App, Databricks Apps) es público por
  default — todo requiere autenticación de la cuenta y permisos explícitos. No
  se otorgó ningún grant adicional sobre el modelo registrado ni el endpoint
  (`CAN_QUERY` queda solo para el creador, el default, verificado con
  `SHOW GRANTS ON FUNCTION workspace.finhive.finhive_agent` → 0 filas) — eso
  solo ya satisface "nadie más lo puede usar".

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
`register_uc_functions.py`): loguea el modelo, lo registra en Unity Catalog, y
llama a `agents.deploy(...)` con `scale_to_zero=True` y `workload_size="Small"`
— uso personal de bajo volumen, minimiza cómputo activo contra la cuota. Los
secrets externos (FRED, Alpha Vantage, Tavily) se pasan al endpoint vía
`environment_vars` con sintaxis `{{secrets/finhive/...}}` — nunca en texto
plano, mismo scope `finhive` que ya usa el notebook de demo.

## Los bugs reales encontrados en el proceso (en orden)

Esta pieza fue, con diferencia, la que más bugs reales encontró de toda la
sesión — cada uno verificado en vivo antes y después del fix, mismo criterio
que ADR 0013/0014.

### 1. FINISH en sub-supervisores de dominio (no solo en el router raíz)

Probando el flujo antes de desplegar, con "¿cuál es el precio actual de
Bitcoin?": el sub-supervisor de `crypto_alt` (`langgraph_supervisor.create_supervisor`)
volvió a invocar a `market_data_worker` después de ya tener el precio, y cerró
con "¿necesitás más información?" sin el dato. Mismo mecanismo que el hallazgo
de FINISH en `top_supervisor._make_supervisor_node` (sesión anterior), pero a
nivel de supervisor de **dominio** — ese fix original solo tocó el router raíz.
Se aplicó el mismo patrón (instrucción + ejemplo concreto) a los 5
sub-supervisores de dominio. Verificado: 5/5 respuestas correctas repitiendo
la pregunta con `thread_id` nuevo cada vez.

### 2. El model-service del AI Gateway no es un `DatabricksServingEndpoint`

Primer intento de deploy: `NOT_FOUND: Dependent serving endpoint
workspace.finhive.finhive_router does not exist`. `AI_GATEWAY_ROUTER_MODEL`
es un model-service de Unity AI Gateway (ADR 0009), no un serving endpoint
clásico — `mlflow.models.resources` no tiene un tipo para esto todavía. Fix:
sacar ese resource, y en cambio pasarle a `get_router_chat_model()` (que arma
un `ChatOpenAI` manual) `DATABRICKS_HOST`/`DATABRICKS_TOKEN` vía
`environment_vars` del endpoint — mismo mecanismo manual que ya usa el
notebook de demo, pero con un **PAT de larga duración (1 año) guardado como
secret** (`{{secrets/finhive/databricks_token}}`) en vez del token efímero del
contexto de notebook (que no existe dentro de un contenedor de serving).

### 3. `log_model(python_model=...)` con path de Windows rompe el contenedor Linux

Corriendo `deploy_agent.py` en local (Windows): el deploy fallaba con
`FileNotFoundError: /model/D:\IMPA\...\chat_agent.py`. Causa raíz, confirmada
leyendo el código fuente de MLflow: `_validate_and_get_model_code_path` hace
`Path(model_code_path).resolve()` — en Windows esto **siempre** devuelve un
path con backslashes, sin importar si el string original pasado era relativo
o absoluto. Del otro lado (el contenedor de serving, Linux),
`_load_context_model_and_signature` hace
`os.path.join(model_path, os.path.basename(conf_model_code_path))`: sobre un
string sin ninguna `/`, el `os.path.basename` de Linux devuelve el string
completo sin cambios — de ahí el path roto. Ninguna variante de path evita
esto corriendo desde Windows. Fix real: correr `log_model()` desde un
notebook de Databricks (`notebooks/01_deploy_agent.py`), donde
`Path(...).resolve()` da un path Linux con `/` real — mismo `deploy_agent.py`,
sin cambios de lógica, solo cambia el entorno de ejecución.

### 4. `sys.stdout.reconfigure()` no existe en el `OutStream` de un notebook

El fix anterior (para el emoji que imprime MLflow al cerrar un run, que
rompía en la consola de Windows) usaba `sys.stdout.reconfigure(...)` — dentro
de un notebook de Databricks, `sys.stdout` es un `OutStream` propio sin ese
método. `AttributeError` visto en vivo. Fix: aplicar solo si
`hasattr(sys.stdout, "reconfigure")`.

### 5. `code_paths` faltante: el contenedor no tenía el paquete `finhive`

Con los bugs 2-4 resueltos, el endpoint desplegó y quedó `READY` — pero
invocarlo de verdad daba `No module named 'finhive'`. `python_model=` solo
empaqueta el archivo de entrada (`chat_agent.py`); `finhive` en sí se instala
en el notebook vía `pip install -e` con el path del Workspace, un editable
install que el contenedor de serving no puede reconstruir (no tiene acceso a
esos archivos). Fix: `code_paths=[".../src/finhive"]` en `log_model()` —
copia el paquete entero dentro del artifact y lo agrega a `sys.path` al
cargar (confirmado leyendo `_copy_file_or_tree`/`_add_code_from_conf_to_system_path`
en el código fuente de MLflow).

### 6. `langgraph`/`langchain` sin pinear en el `requirements.txt` capturado

Con el bug 5 resuelto, invocar el endpoint daba
`cannot import name 'ExecutionInfo' from 'langgraph.runtime'` — el mismo bug
de versión de ADR 0014, pero acá dentro del contenedor de serving. Causa: el
`requirements.txt` que `log_model()` infiere automáticamente solo capturó
`databricks-langchain` y `langchain-openai` como pines explícitos —
`langgraph`/`langchain` quedan como transitivos de `databricks-langchain`,
resueltos de cero al construirse el contenedor, con el mismo riesgo de
"resolver-luck" que ya se vio antes. Fix: `extra_pip_requirements=[...]` en
`log_model()`, forzando los mismos pines exactos ya validados
(`langgraph==1.2.11`, etc.).

### 7. Cuota de "provisioned concurrency" agotada por versiones acumuladas

Los reintentos de deploy (versiones 4, 5, 6 del modelo registrado) no se
retiraban limpiamente al desplegar la siguiente — las tres quedaron contando
contra la cuota de Model Serving de Free Edition simultáneamente, y el sexto
intento falló con `Quota Exceeded: hit the limit for provisioned concurrency
for free usage`, con las versiones anteriores pasando a `DEPLOYMENT_ABORTED`.
Justo el riesgo que motivó revisar cuotas antes de empezar (ver Contexto) —
en este caso vino de reintentos acumulados de un solo endpoint, no de
endpoints sueltos (`databricks serving-endpoints list` mostró un solo
endpoint custom en todo momento). Fix: `databricks serving-endpoints delete`
del endpoint entero y un redeploy limpio de una sola versión — funcionó al
primer intento con todos los fixes anteriores ya aplicados.

## Verificación final

Invocación real contra el endpoint desplegado (HTTP directo, `stream: false`
explícito — el comando `databricks serving-endpoints query` de la CLI devolvía
una respuesta vacía sin `output`, aparentemente por streaming implícito; la
llamada HTTP directa a `/serving-endpoints/.../invocations` sí trae la
respuesta completa):

```
¿Cuál es la tasa de fondos federales actual según FRED?
→ "La tasa de fondos federales actual es 3.63% al 2026-07-01,
   según el analista rates_worker. [...] ¿Hay algo más en lo que
   pueda ayudarte?"
```

Respuesta correcta y grounded, end-to-end: guardrails, memoria, routing y la
tool real de FRED, todo funcionando dentro del endpoint desplegado.

## Consecuencias

- El repo puede mostrarse públicamente sin exponer un endpoint utilizable por
  terceros — la privacidad viene gratis del modelo de permisos de Databricks,
  no de ningún mecanismo agregado ad-hoc.
- `scale_to_zero=True` significa que la primera invocación después de un rato
  de inactividad puede tardar en "despertar" el endpoint — aceptable para uso
  personal, no para una demo en vivo con público esperando respuesta instantánea.
- El PAT guardado como secret (`databricks_token`, vigencia 1 año) es una
  credencial de larga duración real — hay que regenerarlo y volver a
  desplegar cuando expire (o antes, si se sospecha que se filtró).
- `notebooks/01_deploy_agent.py` es ahora la única forma soportada de
  desplegar/actualizar el agent — correr `infra/databricks/deploy_agent.py`
  directo desde una máquina Windows no funciona (hallazgo #3).
- El fix de FINISH en los sub-supervisores de dominio (hallazgo #1) es una
  mejora de calidad real independiente del deploy en sí — mejora también el
  notebook de demo y la evaluación formal (ADR 0014) por igual.

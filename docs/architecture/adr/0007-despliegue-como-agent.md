# ADR 0007 — Despliegue como Agent de Databricks (código listo, no ejecutado acá)

- **Estado**: aceptado
- **Fecha**: 2026-09-01

## Contexto

Pedido explícito del usuario, posterior al pase original del hackathon (que había dejado
esto fuera de alcance a propósito, ver `prompts/non_goals.md` y ADR 0004): desplegar el
agente como un endpoint real de MLflow/Databricks, invocable con requests reales y visible
en la pestaña de Experiments/Serving del workspace. Esta máquina de desarrollo sigue sin
conexión a Databricks (confirmado de nuevo antes de arrancar esto — ver
`prompts/constraints_environment.md`), así que el trabajo acá es escribir el código de
despliegue, no ejecutarlo.

## Decisión

Se replica el patrón de despliegue de finhive (`docs/architecture/adr/finhive-legacy/`,
ADR 0015 — 7 bugs reales encontrados desplegando desde Windows, todos con fix ya conocido)
adaptado a Portfolio Intel:

- `src/portfolio_intel/serving/chat_agent.py` — wrapper `ResponsesAgent` de MLflow sobre
  `build_top_supervisor()`, patrón "models from code". Sin `thread_id`/memoria de sesión
  (a diferencia de finhive): cada invocación del endpoint carga el portfolio actual
  (`load_portfolio_data().get_use_cases()`, backend `databricks` en el endpoint) y
  responde fresco.
- `infra/databricks/deploy_agent.py` — loguea, registra en Unity Catalog
  (`workspace.portfolio_intel.portfolio_intel_agent`) y despliega el modelo, con los mismos
  fixes de Windows/paths/encoding que finhive ya validó en producción. Sin las API keys
  financieras de finhive (no aplican acá) ni el recurso de AI Gateway router (Portfolio
  Intel no usa `get_router_chat_model`); en cambio, fija
  `PORTFOLIO_INTEL_DATA_BACKEND=databricks` como env var del endpoint desplegado -- sin
  esto, el agente serving intentaría leer los CSVs locales de `data/sample_docs/`, que no
  viajan con el modelo (`code_paths` solo empaqueta `src/portfolio_intel/`, no `data/`).
- `notebooks/01_deploy_agent.py` — corre lo de arriba desde un notebook de Databricks
  (Linux), no desde esta máquina Windows -- mismo motivo que documentó finhive: un path
  absoluto de Windows en `mlflow.pyfunc.log_model(python_model=...)` rompe el contenedor
  de serving en Linux.

También se escribió `infra/databricks/setup_catalog.py`: crea `workspace.portfolio_intel`
y sus dos tablas Delta (DDL tipado -- numérico/fecha donde corresponde, no todo `STRING`),
y carga los CSVs sintéticos. La generación de SQL se verificó localmente contra el dataset
real (columnas, tipos, escaping de texto, `NULL`s) sin ejecutar nada -- ver ADR 0003. De
paso se corrigió un bug real en `DatabricksDeltaStore._execute_sql`: devolvía todas las
columnas como string sin castear según el tipo real de la tabla, lo que hubiera roto las
cuentas numéricas de `tools/*.py` (`max impact / projected total investment`, etc.) la
primera vez que se corriera contra este backend -- encontrado por inspección, no en vivo
(no hay forma de ejecutarlo desde acá), así que sigue sin el mismo nivel de confianza que
un bug encontrado corriendo contra Databricks real.

## Consecuencias

- **No verificado end-to-end.** No hay forma de confirmar desde acá que el despliegue
  funcione de verdad -- eso pasa recién corriendo `setup_catalog.py` y después
  `notebooks/01_deploy_agent.py` en un workspace real.
- Dado que finhive ya encontró y documentó 7 bugs reales desplegando prácticamente el
  mismo patrón, es razonable esperar bugs adicionales específicos de este proyecto (nombres
  de tabla, permisos del SQL warehouse, el propio `PORTFOLIO_INTEL_DATA_BACKEND` no
  propagándose como se espera, algo del casteo de tipos de `setup_catalog.py` que no
  calce con lo que `DatabricksDeltaStore` espera) la primera vez que esto corra de verdad
  -- no tratar un fallo en el primer intento como señal de que el código está mal escrito,
  sino como el mismo proceso iterativo que documentan las ADRs de finhive.
- Próximo paso real, en orden: (1) `python infra/databricks/setup_catalog.py` contra el
  workspace real, (2) `notebooks/01_deploy_agent.py`, (3) si algo falla, documentar el bug
  encontrado acá mismo (nueva ADR o ampliar esta), siguiendo la misma disciplina que finhive.

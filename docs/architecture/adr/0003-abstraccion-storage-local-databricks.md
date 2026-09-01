# ADR 0003 — Abstracción de storage: local CSV en dev, Delta en producción

- **Estado**: aceptado
- **Fecha**: 2026-09-01

## Contexto

El usuario pidió explícitamente que el desarrollo sea "agnóstico" de Databricks: esta
máquina no tiene conexión real al workspace (ver `prompts/constraints_environment.md`),
pero el sistema tiene que quedar listo para apuntar a datos reales en Unity Catalog
(Delta) en la compu de trabajo, sin reescribir nada — mismo criterio de decisión única y
centralizada que ya usaba `finhive.config.settings.get_chat_model` para el tiering de
modelos.

## Decisión

`data/store.py` define `PortfolioDataStore` (ABC) con dos implementaciones:

- `LocalCSVStore` — lee `data/sample_docs/{rua_use_case_inventory,ai_use_case_detail}.csv`
  vía pandas. Es la única que corre en esta máquina de desarrollo.
- `DatabricksDeltaStore` — ejecuta SQL contra el SQL warehouse serverless vía
  `databricks.sdk.WorkspaceClient` (mismo patrón que `memory/store.py` de finhive,
  archivado), leyendo `workspace.portfolio_intel.{rua_use_case_inventory,ai_use_case_detail}`.
  Escrita para funcionar de verdad, pero **no ejercitable acá** — ninguna tabla Delta está
  provisionada todavía (fuera de alcance de este pase, ver `prompts/non_goals.md`).

`load_portfolio_data()` es la única factory que el resto del sistema usa, seleccionando el
backend vía `PORTFOLIO_INTEL_DATA_BACKEND` (`local` por default). Todas las tools de
`tools/` reciben un `DataFrame` ya cargado — no conocen ni les importa qué backend lo produjo.

## Consecuencias

- Todo el núcleo determinista (ADR 0002) y sus 29 tests unitarios corren contra
  `LocalCSVStore` sin ningún cambio de código necesario para correr después contra
  `DatabricksDeltaStore` — el cambio es una variable de entorno.
- El esquema de columnas (`data/schema.py`) es el contrato real entre ambos backends: si
  el CSV local y las tablas Delta alguna vez divergen en nombres de columna, el bug
  aparece ahí, no en la lógica de negocio.
- **Actualización (ADR 0007)**: `infra/databricks/setup_catalog.py` ya escribe el DDL de
  las dos tablas Delta y carga los CSVs sintéticos -- generación de SQL verificada
  localmente contra el dataset real (columnas, tipos, escaping, NULLs), pero **la
  ejecución contra un workspace real sigue sin probarse** desde acá, mismo motivo de
  siempre. `DatabricksDeltaStore._execute_sql` también se corrigió para castear columnas
  numéricas/fecha según el tipo real de la tabla (`manifest.schema.columns[i].type_name`)
  -- sin eso, todo llegaba como string y las cuentas de `tools/*.py` (`max impact / 
  projected total investment`, etc.) hubieran roto contra este backend aunque anduvieran
  bien contra `LocalCSVStore` (donde pandas infiere tipos del CSV).

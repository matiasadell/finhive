# ADR 0008 — Secrets vía Databricks Secrets, no solo `.env`

- **Estado**: aceptado
- **Fecha**: 2026-09-01

## Contexto

`DATABRICKS_HOST`/`DATABRICKS_TOKEN`/`SQL_WAREHOUSE_ID` vivían solo en `.env` (ver ADR
0007). Pedido explícito del usuario, ya que el destino real es Databricks: centralizar
esos 3 valores en un secret scope real (`portfolio_intel`) en vez de que cada persona los
tenga sueltos en su `.env` local.

Restricción real del SDK (verificada localmente antes de escribir nada): Databricks solo
deja **leer** el valor de un secret vía el `dbutils` que el runtime inyecta dentro de un
notebook/job/endpoint de serving -- `WorkspaceClient().dbutils` (la versión remota del SDK)
no expone `.secrets` en absoluto, solo `.widgets`. Escribir/crear scope sí es remoto
(`WorkspaceClient().secrets.create_scope/put_secret`), leer no.

## Decisión

- `infra/databricks/setup_secrets.py` (nuevo): crea el scope `portfolio_intel` (idempotente)
  y carga los 3 secrets, leyéndolos de las mismas env vars que ya usaba `.env.example` —
  nunca imprime un valor.
- `config/settings.py` sigue leyendo `os.getenv(...)` para los 3 valores -- no cambia, y no
  puede cambiar a leer secrets directo por la restricción de arriba. Lo que cambia es de
  dónde sale esa env var según el contexto:
  - Notebook (`notebooks/01_deploy_agent.py`): la carga con el `dbutils` ambiente
    (`dbutils.secrets.get(scope="portfolio_intel", key=...)`).
  - Endpoint de serving desplegado (`infra/databricks/deploy_agent.py`): `environment_vars`
    ahora pasa referencias `{{secrets/portfolio_intel/...}}`, que Databricks resuelve a
    valores reales al arrancar el contenedor -- no más valores literales calculados en
    tiempo de deploy.
  - Esta máquina de desarrollo: sigue siendo `.env`, porque no hay ni notebook ni endpoint
    acá.

## Consecuencias

- Un solo lugar de verdad (`portfolio_intel/databricks_host`,
  `.../databricks_token`, `.../sql_warehouse_id`) en vez de cada `.env` local
  desincronizándose.
- `setup_secrets.py` sigue sin poder ejecutarse ni verificarse desde acá (mismo motivo que
  el resto de `infra/databricks/`, ver ADR 0007) -- se corre una vez, antes que
  `setup_catalog.py` y `deploy_agent.py`, con las env vars locales del que lo corre.
- Si alguna vez se agrega un secret nuevo, el patrón es: agregarlo a `_SECRETS` en
  `setup_secrets.py`, agregar su getter en `config/settings.py` (mismo estilo que
  `get_databricks_token`), y si hace falta en el endpoint desplegado, agregar su
  referencia `{{secrets/...}}` en `deploy_agent.py`.

# ADR 0008 — Secrets vía Databricks Secrets, no solo `.env`

- **Estado**: aceptado
- **Fecha**: 2026-09-01

## Contexto

`DATABRICKS_HOST`/`DATABRICKS_TOKEN`/`SQL_WAREHOUSE_ID` vivían solo en `.env` (ver ADR
0007). Pedido explícito del usuario, ya que el destino real es Databricks: centralizar
esos 3 valores en un secret scope real (`portfolio_intel`) en vez de que cada persona los
tenga sueltos en su `.env` local.

Corrección real a mitad de esto: la primera versión asumía que un secret solo se puede
leer desde el `dbutils` de una celda de notebook. Confirmado por el usuario contra
Databricks real: `databricks.sdk.runtime.dbutils` (no `WorkspaceClient().dbutils`, que es
una versión remota reducida sin `.secrets`) da el `dbutils` completo -- con `.secrets`
incluido -- en cualquier `.py` que corra de verdad sobre compute de Databricks, sea celda
de notebook o módulo importado. Eso es justo el caso de `config/settings.py`.

## Decisión

- `infra/databricks/setup_secrets.py` (nuevo): crea el scope `portfolio_intel`
  (idempotente) y carga los 3 secrets, leyéndolos de las mismas env vars que ya usaba
  `.env.example` -- nunca imprime un valor.
- `config/settings.py` — `_read_secret(key)` intenta
  `databricks.sdk.runtime.dbutils.secrets.get(scope=SECRET_SCOPE, key=key)` primero;
  afuera de Databricks eso tira (import o auth), se atrapa entero y devuelve `None`. Cada
  getter (`get_databricks_host`, etc.) usa `_read_secret(...) or os.getenv(...)` -- el
  secret gana cuando existe, `.env` sigue funcionando donde no hay Databricks real.
- Endpoint de serving desplegado (`infra/databricks/deploy_agent.py`): caso aparte, un
  contenedor de Model Serving no es compute de Databricks con `dbruntime` -- ahí
  `environment_vars` pasa referencias `{{secrets/portfolio_intel/...}}`, que Databricks
  resuelve a valores reales al arrancar el contenedor, no vía `dbutils`.

## Consecuencias

- `notebooks/01_deploy_agent.py` no necesita copiar secrets a `os.environ` a mano --
  `config/settings.py` los lee solo. Solo queda seteando `PORTFOLIO_INTEL_DATA_BACKEND`
  (no es un secret).
- Un solo lugar de verdad (`portfolio_intel/databricks_host`, `.../databricks_token`,
  `.../sql_warehouse_id`) en vez de cada `.env` local desincronizándose.
- `setup_secrets.py` sigue sin poder ejecutarse ni verificarse desde acá (mismo motivo que
  el resto de `infra/databricks/`, ver ADR 0007) -- se corre una vez, antes que
  `setup_catalog.py` y `deploy_agent.py`, con las env vars locales del que lo corre.
- Si alguna vez se agrega un secret nuevo, el patrón es: agregarlo a `_SECRETS` en
  `setup_secrets.py`, agregar su getter en `config/settings.py` (mismo estilo, vía
  `_read_secret(...) or os.getenv(...)`), y si hace falta en el endpoint desplegado,
  agregar su referencia `{{secrets/...}}` en `deploy_agent.py`.

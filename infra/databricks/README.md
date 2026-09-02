# infra/databricks/

Scripts de infraestructura (Python + `databricks-sdk`, sin Terraform ni Asset Bundles),
escritos pero **no ejecutados** desde esta máquina de desarrollo -- sin conexión real a
Databricks (ver `prompts/constraints_environment.md`). Correr en orden, en la compu de
trabajo o desde un notebook de Databricks:

1. **`setup_secrets.py`** — crea el secret scope `portfolio_intel` y carga ahí
   `databricks_host`/`databricks_token`/`sql_warehouse_id`, leyéndolos de las mismas
   env vars que `.env.example`. Ver ADR 0008.
2. **`setup_catalog.py`** — crea `workspace.portfolio_intel` y sus dos tablas Delta
   (`rua_use_case_inventory`, `ai_use_case_detail`, DDL tipado según
   `src/portfolio_intel/data/schema.py`), y carga los CSVs sintéticos de
   `data/sample_docs/` (idempotente: `TRUNCATE` + re-insert). Ver ADR 0007.
3. **`deploy_agent.py`** — loguea, registra en Unity Catalog y despliega Portfolio Intel
   como Agent de Databricks (Mosaic AI Agent Framework), vía
   `src/portfolio_intel/serving/chat_agent.py`. Correr desde un notebook de Databricks, no
   desde Windows (ver el docstring del script y `notebooks/01_deploy_agent.py`) — mismos
   fixes de path/encoding que ya documentó finhive (ADR 0015 archivada). El endpoint
   desplegado recibe `DATABRICKS_HOST`/`DATABRICKS_TOKEN`/`SQL_WAREHOUSE_ID` como
   referencias al secret scope, no como valores literales.

Ninguno de los tres se ejecutó desde esta sesión: la generación de SQL/DDL de
`setup_catalog.py` se validó localmente contra el dataset real (sin ejecutar contra
Databricks), y `deploy_agent.py`/`setup_secrets.py` se validaron solo hasta donde se
puede sin red (imports, sintaxis). Ver ADR 0007/0008 para el detalle completo y los
pasos pendientes.

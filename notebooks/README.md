# notebooks/

- `00_demo.py` — script Python plano (no celdas de notebook Databricks): corre 4
  escenarios end-to-end contra Portfolio Intel (reporte ejecutivo determinista + los 4
  agentes de dominio), escribe los outputs en `outputs/`. Corre tal cual local
  (`python notebooks/00_demo.py`) y también sirve, sin cambios, como notebook de
  Databricks Repos una vez sincronizado ahí.
- `01_deploy_agent.py` — notebook de Databricks (celdas `# COMMAND`, con `%pip`/`dbutils`)
  que corre `infra/databricks/deploy_agent.py` para registrar y desplegar Portfolio Intel
  como Agent real, y prueba el endpoint desplegado. Tiene que correr desde Databricks
  (Linux), no desde esta máquina Windows -- ver el docstring del propio notebook y ADR
  0007. Requiere `infra/databricks/setup_catalog.py` ya corrido antes.

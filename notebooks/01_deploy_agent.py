# Databricks notebook source
# MAGIC %md
# MAGIC # Portfolio Intel — Deploy como Agent (Mosaic AI Agent Framework)
# MAGIC
# MAGIC Corre `infra/databricks/deploy_agent.py` desde acá, no desde una máquina local —
# MAGIC necesario porque `mlflow.pyfunc.log_model(python_model=...)` resuelve el path del
# MAGIC código a una ruta absoluta con `Path(...).resolve()`. En Windows eso siempre da un
# MAGIC path con backslashes (`D:\...`); en el lado del serving (Linux), un path así se
# MAGIC interpreta mal y el contenedor termina buscando un archivo que no existe (mismo
# MAGIC hallazgo real que documentó finhive, ADR 0015 archivada). Corriendo este mismo
# MAGIC script desde acá (Linux), `Path(...).resolve()` da un path con `/` real, y el
# MAGIC problema no existe.
# MAGIC
# MAGIC No hay ningún cambio de lógica entre correrlo acá o en local — es el mismo
# MAGIC `infra/databricks/deploy_agent.py`, importado tal cual.

# COMMAND ----------

# Ruta del Repo en este workspace. Ajustar al path real donde está clonado.
REPO_PATH = "/Workspace/Users/<tu-usuario>/portfolio-intel"

# COMMAND ----------

# MAGIC %pip install -e {REPO_PATH} --no-deps

# COMMAND ----------

# MAGIC %pip install "langgraph==1.2.11" "langgraph-prebuilt==1.1.0" "langgraph-checkpoint==4.2.0" "langchain==1.3.18" "langchain-core==1.6.1" "databricks-langchain==0.20.0" "langgraph-supervisor==0.0.31" "mlflow[databricks]>=3.1.0"

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

import sys

REPO_PATH = "/Workspace/Users/<tu-usuario>/portfolio-intel"
sys.path.insert(0, f"{REPO_PATH}/src")
sys.path.insert(0, f"{REPO_PATH}/infra/databricks")

# COMMAND ----------

# MAGIC %md ## Config — backend de datos + secrets
# MAGIC
# MAGIC Los secrets (`databricks_host`, `databricks_token`, `sql_warehouse_id`) tienen
# MAGIC que estar ya cargados en el scope `portfolio_intel`
# MAGIC (`infra/databricks/setup_secrets.py`, corrido una vez antes de esto). Acá se leen
# MAGIC con el `dbutils` ambiente del notebook y se cargan como env vars -- es la única
# MAGIC forma de leer un secret (Databricks no lo deja remoto vía SDK, ver
# MAGIC `config/settings.py`).

# COMMAND ----------

import os

os.environ["PORTFOLIO_INTEL_DATA_BACKEND"] = "databricks"
os.environ["DATABRICKS_HOST"] = dbutils.secrets.get(scope="portfolio_intel", key="databricks_host")
os.environ["DATABRICKS_TOKEN"] = dbutils.secrets.get(scope="portfolio_intel", key="databricks_token")
os.environ["SQL_WAREHOUSE_ID"] = dbutils.secrets.get(scope="portfolio_intel", key="sql_warehouse_id")

print("Config cargada (valores no impresos).")

# COMMAND ----------

# MAGIC %md ## Loguear, registrar y desplegar
# MAGIC
# MAGIC `mlflow.pyfunc.log_model` corre una predicción real sobre el input de ejemplo para
# MAGIC validar el modelo -- esta celda invoca el grafo completo al menos una vez (necesita
# MAGIC las tablas Delta `workspace.portfolio_intel.*` ya provisionadas y con datos, ver
# MAGIC `infra/databricks/README.md`).

# COMMAND ----------

import deploy_agent

deploy_agent.main()

# COMMAND ----------

# MAGIC %md ## Verificación de permisos
# MAGIC
# MAGIC Confirmar que no haya grants adicionales sobre el modelo registrado -- solo el
# MAGIC creador debería tener acceso.

# COMMAND ----------

grants = spark.sql("SHOW GRANTS ON FUNCTION workspace.portfolio_intel.portfolio_intel_agent").collect()
print(f"Grants explícitos sobre el modelo: {len(grants)}")
for g in grants:
    print(g)

# COMMAND ----------

# MAGIC %md ## Probar el endpoint desplegado
# MAGIC
# MAGIC Una vez que `deploy_agent.main()` termina, el endpoint tarda unos minutos en
# MAGIC quedar `READY` (visible en la pestaña **Serving** del workspace). Con eso:

# COMMAND ----------

from mlflow.deployments import get_deploy_client

client = get_deploy_client("databricks")
response = client.predict(
    endpoint="portfolio_intel_agent",  # el nombre real lo imprime deploy_agent.main() arriba
    inputs={"input": [{"role": "user", "content": "¿Qué casos de uso deberíamos priorizar?"}]},
)
print(response)

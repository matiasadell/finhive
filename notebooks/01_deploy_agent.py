# Databricks notebook source
# MAGIC %md
# MAGIC # FinHive — Deploy como Agent (Mosaic AI Agent Framework)
# MAGIC
# MAGIC Corre `infra/databricks/deploy_agent.py` desde acá, no desde una máquina local —
# MAGIC necesario porque `mlflow.pyfunc.log_model(python_model=...)` resuelve el path del
# MAGIC código a una ruta absoluta con `Path(...).resolve()`. En Windows eso siempre da un
# MAGIC path con backslashes (`D:\...`); en el lado del serving (Linux), `os.path.basename()`
# MAGIC de un string sin ninguna `/` devuelve el string completo sin cambios, así que el
# MAGIC contenedor termina buscando literalmente `/model/D:\...` y falla con
# MAGIC `FileNotFoundError` (visto en vivo, ADR 0015). Corriendo este mismo script desde acá
# MAGIC (Linux), `Path(...).resolve()` da un path con `/` real, y el problema no existe.
# MAGIC
# MAGIC No hay ningún cambio de lógica entre correrlo acá o en local — es el mismo
# MAGIC `infra/databricks/deploy_agent.py`, importado tal cual.

# COMMAND ----------

# Ruta del Repo en este workspace. Si clonaste el repo en otro path, ajustar acá.
REPO_PATH = "/Workspace/Users/matiasadell@hotmail.com/finhive"

# COMMAND ----------

# MAGIC %pip install -e {REPO_PATH} --no-deps

# COMMAND ----------

# MAGIC %pip install "langgraph==1.2.11" "langgraph-prebuilt==1.1.0" "langgraph-checkpoint==4.2.0" "langchain==1.3.18" "langchain-core==1.6.1" "langchain-openai==1.6.0" "databricks-langchain==0.20.0" "langgraph-supervisor==0.0.31" "mlflow[databricks]>=3.1.0"

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

import sys

REPO_PATH = "/Workspace/Users/matiasadell@hotmail.com/finhive"
sys.path.insert(0, f"{REPO_PATH}/src")
sys.path.insert(0, f"{REPO_PATH}/infra/databricks")

# COMMAND ----------

# MAGIC %md ## Credenciales — mismo patrón que `00_demo.py`

# COMMAND ----------

import os

os.environ["FRED_API_KEY"] = dbutils.secrets.get(scope="finhive", key="fred_api_key")
os.environ["ALPHA_VANTAGE_API_KEY"] = dbutils.secrets.get(scope="finhive", key="alpha_vantage_api_key")
os.environ["TAVILY_API_KEY"] = dbutils.secrets.get(scope="finhive", key="tavily_api_key")
os.environ["SEC_EDGAR_USER_AGENT"] = "FinHive research-agent matiasadell@hotmail.com"

_ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
os.environ["DATABRICKS_HOST"] = _ctx.apiUrl().get()
os.environ["DATABRICKS_TOKEN"] = _ctx.apiToken().get()

print("Credenciales cargadas en el entorno (valores no impresos).")

# COMMAND ----------

# MAGIC %md ## Loguear, registrar y desplegar
# MAGIC
# MAGIC `mlflow.pyfunc.log_model` corre una predicción real sobre el input de ejemplo para
# MAGIC validar el modelo -- esta celda invoca el grafo completo al menos una vez.

# COMMAND ----------

import deploy_agent

deploy_agent.main()

# COMMAND ----------

# MAGIC %md ## Verificación de permisos
# MAGIC
# MAGIC Confirmar que no haya grants adicionales sobre el modelo registrado -- solo el
# MAGIC creador debería tener acceso (ver ADR 0015).

# COMMAND ----------

grants = spark.sql("SHOW GRANTS ON FUNCTION workspace.finhive.finhive_agent").collect()
print(f"Grants explícitos sobre el modelo: {len(grants)}")
for g in grants:
    print(g)

# Databricks notebook source
# MAGIC %md
# MAGIC # FinHive — Demo interactiva
# MAGIC
# MAGIC Corre el sistema jerárquico completo (top-level supervisor → 5 supervisores de
# MAGIC dominio → 13 workers ReAct) directamente en un notebook de Databricks, contra
# MAGIC los Foundation Model APIs nativos (gratis en Free Edition) y las APIs de datos
# MAGIC reales de cada dominio.
# MAGIC
# MAGIC **Antes de correr esto**: las keys de FRED / Alpha Vantage / Tavily ya están
# MAGIC cargadas en el secret scope `finhive` (`databricks secrets list-secrets finhive`
# MAGIC para confirmar). SEC EDGAR, yfinance y CoinGecko no necesitan key.
# MAGIC
# MAGIC **Ojo con la cuota**: Alpha Vantage (News & Sentiment) tiene free tier chico
# MAGIC (~25 requests/día) y CoinGecko (Crypto) rate-limitea uso anónimo intensivo — no
# MAGIC hace falta correr las 6 celdas de prueba muchas veces seguidas.

# COMMAND ----------

# MAGIC %md ## 1. Instalar el paquete (modo editable, desde este mismo Repo)

# COMMAND ----------

# Ruta del Repo en este workspace. Si clonaste el repo en otro path, ajustar acá.
REPO_PATH = "/Workspace/Users/matiasadell@hotmail.com/finhive"

# COMMAND ----------

# MAGIC %md
# MAGIC **Ojo con las versiones**: `pyproject.toml` declara rangos abiertos
# MAGIC (`langgraph>=0.3`, sin tope superior) — un `%pip install -e` resuelve el
# MAGIC árbol de dependencias de cero cada vez que corre, y no hay garantía de
# MAGIC que aterrice siempre en la misma combinación (visto en vivo: una
# MAGIC reinstalación en medio de una sesión de debugging bajó a
# MAGIC `langgraph==1.0.10` / `langgraph-prebuilt==1.0.13`, incompatibles entre sí
# MAGIC — `ImportError: cannot import name 'ExecutionInfo' from
# MAGIC 'langgraph.runtime'`). Para evitarlo, se instala `finhive` sin resolver
# MAGIC dependencias (`--no-deps`) y después se clavan las versiones exactas ya
# MAGIC validadas en `uv.lock` — la misma combinación que usa el entorno local.

# COMMAND ----------

# MAGIC %pip install -e {REPO_PATH} --no-deps

# COMMAND ----------

# MAGIC %pip install "langgraph==1.2.11" "langgraph-prebuilt==1.1.0" "langgraph-checkpoint==4.2.0" "langchain==1.3.18" "langchain-core==1.6.1" "databricks-langchain==0.20.0" "langgraph-supervisor==0.0.31"

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

import sys

# Red de seguridad: el editable install de arriba a veces no queda resuelto
# por el import system después de este restart en cómputo Serverless (visto
# en vivo: `pip show finhive` confirmaba el paquete instalado, pero
# `importlib.util.find_spec("finhive")` devolvía `None` igual). Se agrega
# `src/` directo al `sys.path` acá, inmediatamente después del restart —no
# en la celda que arma el grafo— para que quede resuelto sin importar a qué
# sección saltes después (ej. probar el AI Gateway sin haber armado el
# grafo todavía). `REPO_PATH` no sobrevive al restart de la celda anterior,
# así que se redefine acá.
REPO_PATH = "/Workspace/Users/matiasadell@hotmail.com/finhive"
sys.path.insert(0, f"{REPO_PATH}/src")

# COMMAND ----------

# MAGIC %md ## 2. Credenciales — desde Databricks Secrets, no desde un `.env`
# MAGIC
# MAGIC En local, `finhive.config.settings` lee estas keys de variables de entorno
# MAGIC (cargadas desde `.env` con `python-dotenv`). Acá no hay `.env` — se cargan las
# MAGIC mismas variables de entorno, pero con el valor real leído de forma nativa desde
# MAGIC el secret scope de Databricks (`dbutils.secrets.get`), nunca hardcodeado ni
# MAGIC impreso en ninguna celda.

# COMMAND ----------

import os

os.environ["FRED_API_KEY"] = dbutils.secrets.get(scope="finhive", key="fred_api_key")
os.environ["ALPHA_VANTAGE_API_KEY"] = dbutils.secrets.get(scope="finhive", key="alpha_vantage_api_key")
os.environ["TAVILY_API_KEY"] = dbutils.secrets.get(scope="finhive", key="tavily_api_key")
os.environ["SEC_EDGAR_USER_AGENT"] = "FinHive research-agent matiasadell@hotmail.com"

# El top-level supervisor pasa por Unity AI Gateway (routing real entre dos
# modelos, ver ADR 0009/0010) vía un cliente OpenAI-compatible, que necesita
# host + token. Acá, en vez de un secret estático, se usa el contexto propio
# de esta ejecución del notebook -- un token de corta duración, sin
# necesidad de generar ni guardar ningún PAT.
_ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
os.environ["DATABRICKS_HOST"] = _ctx.apiUrl().get()
os.environ["DATABRICKS_TOKEN"] = _ctx.apiToken().get()

print("Credenciales cargadas en el entorno (valores no impresos).")

# COMMAND ----------

# MAGIC %md ## 3. Armar el grafo jerárquico completo

# COMMAND ----------

import mlflow
import mlflow.langchain

mlflow.langchain.autolog()

from finhive.graph import build_top_supervisor

graph = build_top_supervisor()
print("Grafo jerárquico compilado: 5 equipos de dominio listos.")

# COMMAND ----------


def ask(question: str) -> None:
    """Invoca el supervisor raíz y muestra qué equipos respondieron y la respuesta final."""
    result = graph.invoke({"messages": [("user", question)]})
    teams = [m.name for m in result["messages"] if getattr(m, "name", None) and str(m.name).endswith("_team")]
    print(f"Pregunta: {question}")
    print(f"Equipos invocados: {teams}")
    print(f"Respuesta:\n{result['messages'][-1].content}")
    print("-" * 80)


# COMMAND ----------

# MAGIC %md ## 4. Unity AI Gateway: model routing real (bonus)
# MAGIC
# MAGIC El supervisor raíz de arriba ya usa esto por dentro (`get_router_chat_model`),
# MAGIC pero acá se ve explícito: el `model-service` `workspace.finhive.finhive_router`
# MAGIC reparte tráfico 70% Llama 3.3 70B / 30% GPT OSS 120B — correr esta celda varias
# MAGIC veces y mirar el campo `modelo real usado` para verlo variar.

# COMMAND ----------

from finhive.config.settings import get_gateway_embeddings, get_router_chat_model

router_llm = get_router_chat_model()
for _ in range(4):
    resp = router_llm.invoke("Respondé con una sola palabra: OK")
    print("modelo real usado:", resp.response_metadata.get("model_name"))

embeddings = get_gateway_embeddings()
vector = embeddings.embed_query("ejemplo de texto financiero")
print(f"\nEmbeddings (workspace.finhive.finhive_embeddings): vector de {len(vector)} dimensiones")

# COMMAND ----------

# MAGIC %md ## 5. Una pregunta por dominio

# COMMAND ----------

ask("¿Cuál es la tasa de fondos federales actual según FRED?")

# COMMAND ----------

ask("¿Cuál es el P/E actual de Apple (AAPL)?")

# COMMAND ----------

ask("¿Cuál es la volatilidad anualizada de un portfolio 50% AAPL y 50% MSFT en los últimos 6 meses?")

# COMMAND ----------

ask("¿Cuándo es el próximo reporte de earnings de Apple (AAPL)?")

# COMMAND ----------

ask("¿Cuál es el precio actual de Bitcoin?")

# COMMAND ----------

# MAGIC %md ## 6. Una pregunta que cruza dos dominios
# MAGIC
# MAGIC El router del top-level supervisor tiene que decidir delegar a los dos equipos
# MAGIC correspondientes, uno por vez (ver ADR 0005 y ADR 0006 sobre cómo se afinó este
# MAGIC comportamiento).

# COMMAND ----------

ask(
    "¿Cuál es la tasa de fondos federales actual, y cuál es el P/E de Apple (AAPL)?"
)

# COMMAND ----------

# MAGIC %md ## 7. Ver las trazas en MLflow
# MAGIC
# MAGIC `mlflow.langchain.autolog()` ya quedó activo desde la celda 3 — cada invocación
# MAGIC de arriba generó una traza completa (cada nodo del grafo, cada tool call, cada
# MAGIC llamada al LLM). Abrí la pestaña **Experiments** de este notebook, o el panel de
# MAGIC **Traces** en MLflow, para inspeccionarlas.

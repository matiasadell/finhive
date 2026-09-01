"""Registra y despliega Portfolio Intel como Agent de Databricks (Mosaic AI Agent Framework).

Envuelve `build_top_supervisor()` con `portfolio_intel.serving.chat_agent.PortfolioIntelAgent`
(interfaz `ResponsesAgent` de MLflow) y lo publica como un serving endpoint real,
para que aparezca en la pestaña **Agents**/Experiments de MLflow del workspace.

Adaptado de `infra/databricks/deploy_agent.py` de finhive
(`docs/architecture/adr/finhive-legacy/`, ADR 0015) -- ese script documenta 7
bugs reales encontrados desplegando desde Windows contra Databricks; los
fixes de acá son los mismos, no bugs nuevos de este proyecto. Diferencias
reales con la versión de finhive: sin las API keys financieras (FRED/Alpha
Vantage/Tavily/SEC EDGAR) ni el recurso de AI Gateway router (este proyecto
no usa `get_router_chat_model`) -- en cambio, `PORTFOLIO_INTEL_DATA_BACKEND`
tiene que quedar en `databricks` en el endpoint desplegado (ver
`config/settings.get_data_backend`), si no el agente serving intentaría leer
los CSVs locales de `data/sample_docs/`, que no viajan con el modelo.

Privacidad: no se otorga ningún grant adicional sobre el modelo registrado ni
sobre el endpoint -- por default, solo el creador tiene `CAN_QUERY`.

`scale_to_zero=True` y `workload_size="Small"`: uso de demo/hackathon de bajo
volumen, no tráfico de producción real -- minimiza cómputo activo.

**Correr esto desde un notebook de Databricks (`notebooks/01_deploy_agent.py`),
no desde esta máquina de desarrollo ni desde Windows en general** -- ver el
comentario sobre `_CHAT_AGENT_PATH` más abajo y el propio notebook para el
motivo (separadores de path de Windows rompen el contenedor de serving en
Linux). Esta máquina tampoco tiene conexión a Databricks para intentarlo
igual (ver `prompts/constraints_environment.md`).

Uso (desde la raíz del repo, en un notebook/entorno con conexión real):
    python infra/databricks/deploy_agent.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# La consola de Windows por default no maneja bien los emojis que MLflow
# imprime al terminar un run (ej. "🏃 View run..."), y tira
# UnicodeEncodeError con la codepage cp1252 -- corta el script después de
# loguear el modelo pero antes de registrarlo/desplegarlo (mismo hallazgo
# que documentó finhive, ADR 0015). `reconfigure` no existe en el
# `OutStream` propio que usa un notebook de Databricks -- ahí no hace falta
# igual (Linux, UTF-8 por default), así que se aplica solo si está disponible.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import mlflow
from mlflow.models.resources import DatabricksServingEndpoint, DatabricksSQLWarehouse

from portfolio_intel.config.settings import (
    SUPERVISOR_MODEL_ENDPOINT,
    UC_CATALOG,
    UC_SCHEMA,
    WORKER_MODEL_ENDPOINT,
    get_sql_warehouse_id,
)

# Relativo al cwd, no absoluto: `mlflow.pyfunc.log_model(python_model=...)`
# guarda ese path tal cual en los metadatos del modelo ("models from code").
# Con un path absoluto de Windows (`D:\...`), el contenedor de serving en
# Linux intentaba abrir literalmente `/model/D:\...` y fallaba con
# FileNotFoundError (visto en vivo por finhive, ADR 0015). `.as_posix()`
# además: `os.path.relpath` en Windows devuelve separadores `\`, que en
# Linux no son separador de path sino un carácter más del nombre de archivo
# -- sin esto, mismo error con otra forma. Asume que el script corre desde
# la raíz del repo, como dice `Uso:` arriba -- y en la práctica, desde un
# notebook de Databricks (Linux), no desde Windows (ver el docstring).
_REPO_ROOT = Path(__file__).resolve().parents[2]
_CHAT_AGENT_ABS_PATH = _REPO_ROOT / "src" / "portfolio_intel" / "serving" / "chat_agent.py"
_CHAT_AGENT_PATH = Path(os.path.relpath(_CHAT_AGENT_ABS_PATH, start=os.getcwd())).as_posix()
# El paquete `portfolio_intel` entero (no solo chat_agent.py) tiene que
# viajar con el modelo -- `python_model=` solo empaqueta ese único archivo.
# `code_paths` copia el directorio entero dentro del artifact y lo agrega a
# `sys.path` del contenedor de serving.
_PORTFOLIO_INTEL_PACKAGE_PATH = str(_REPO_ROOT / "src" / "portfolio_intel")
_MODEL_NAME = f"{UC_CATALOG}.{UC_SCHEMA}.portfolio_intel_agent"


def main() -> None:
    from portfolio_intel.config.settings import get_databricks_workspace_email

    mlflow.set_tracking_uri("databricks")
    mlflow.set_registry_uri("databricks-uc")
    # Corriendo desde fuera de un notebook no hay experimento implícito --
    # sin esto, mlflow.start_run() falla con "Could not find experiment with
    # ID None" (mismo hallazgo que finhive, ADR 0015).
    mlflow.set_experiment(f"/Users/{get_databricks_workspace_email()}/portfolio-intel-deploy")

    with mlflow.start_run(run_name="portfolio-intel-agent-deploy"):
        logged_model = mlflow.pyfunc.log_model(
            python_model=_CHAT_AGENT_PATH,
            name="agent",
            code_paths=[_PORTFOLIO_INTEL_PACKAGE_PATH],
            resources=[
                DatabricksServingEndpoint(endpoint_name=SUPERVISOR_MODEL_ENDPOINT),
                DatabricksServingEndpoint(endpoint_name=WORKER_MODEL_ENDPOINT),
                DatabricksSQLWarehouse(warehouse_id=get_sql_warehouse_id()),
            ],
            # La inferencia automática de dependencias de log_model no
            # captura langgraph/langchain como pines explícitos -- quedan
            # como transitivos de databricks-langchain, resueltos de cero al
            # construirse el contenedor de serving, con el mismo riesgo de
            # "resolver-luck" que ya documentó finhive (ImportError:
            # ExecutionInfo, ver ADR 0015 archivada, y el propio hallazgo de
            # este proyecto en `pyproject.toml`/CLAUDE.md). Se fuerzan los
            # mismos pines exactos ya validados localmente.
            extra_pip_requirements=[
                "langgraph==1.2.11",
                "langgraph-prebuilt==1.1.0",
                "langgraph-checkpoint==4.2.0",
                "langchain==1.3.18",
                "langchain-core==1.6.1",
                "langgraph-supervisor==0.0.31",
                "databricks-langchain==0.20.0",
            ],
        )
        print(f"Modelo logueado: {logged_model.model_uri}")

    registered = mlflow.register_model(logged_model.model_uri, name=_MODEL_NAME)
    print(f"Registrado en Unity Catalog: {_MODEL_NAME} versión {registered.version}")

    from databricks import agents

    deployment = agents.deploy(
        model_name=_MODEL_NAME,
        model_version=int(registered.version),
        scale_to_zero=True,
        workload_size="Small",
        environment_vars={
            # Sin esto, el endpoint desplegado intentaría leer los CSVs
            # locales de data/sample_docs/ (default "local"), que no viajan
            # con el modelo -- tiene que leer las tablas Delta reales.
            "PORTFOLIO_INTEL_DATA_BACKEND": "databricks",
            "SQL_WAREHOUSE_ID": get_sql_warehouse_id(),
        },
    )
    print(f"Endpoint desplegado: {deployment.endpoint_name}")
    print(
        "Recordatorio: no otorgar ningún grant adicional sobre "
        f"'{_MODEL_NAME}' ni sobre el endpoint -- por default solo el "
        "creador puede invocarlo (CAN_QUERY)."
    )


if __name__ == "__main__":
    main()

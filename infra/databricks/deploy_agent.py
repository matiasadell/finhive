# Registra y despliega Portfolio Intel como Agent de Databricks (Mosaic AI Agent
# Framework). Correr desde un notebook de Databricks (notebooks/01_deploy_agent.py),
# no desde Windows -- un path absoluto de Windows rompe el contenedor de serving.
# Uso: python infra/databricks/deploy_agent.py

from __future__ import annotations

import os
import sys
from pathlib import Path

# Windows: la consola no maneja bien los emojis que imprime MLflow al cerrar
# un run -- UnicodeEncodeError con cp1252. No hace falta en un notebook (Linux, UTF-8).
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

# Relativo al cwd, no absoluto -- un path de Windows rompe el contenedor de
# serving (Linux) al resolver python_model=. .as_posix() por los backslashes.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_CHAT_AGENT_ABS_PATH = _REPO_ROOT / "src" / "portfolio_intel" / "serving" / "chat_agent.py"
_CHAT_AGENT_PATH = Path(os.path.relpath(_CHAT_AGENT_ABS_PATH, start=os.getcwd())).as_posix()
# code_paths empaqueta el paquete entero -- python_model= solo trae ese archivo.
_PORTFOLIO_INTEL_PACKAGE_PATH = str(_REPO_ROOT / "src" / "portfolio_intel")
_MODEL_NAME = f"{UC_CATALOG}.{UC_SCHEMA}.portfolio_intel_agent"


def main() -> None:
    from portfolio_intel.config.settings import get_databricks_workspace_email

    mlflow.set_tracking_uri("databricks")
    mlflow.set_registry_uri("databricks-uc")
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
            # Pines exactos ya validados localmente -- la inferencia automática
            # de deps no los captura, quedan transitivos y con riesgo de resolver mal.
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

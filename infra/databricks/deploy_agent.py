"""Registra y despliega FinHive como Agent de Databricks (Mosaic AI Agent Framework).

Envuelve `build_top_supervisor()` con `finhive.serving.chat_agent.FinHiveAgent`
(interfaz `ResponsesAgent` de MLflow) y lo publica como un serving endpoint real,
para que aparezca en la pestaña Agents de Databricks (ver ADR 0015).

Privacidad: no se otorga ningún grant adicional sobre el modelo registrado ni
sobre el endpoint -- por default, solo el creador tiene `CAN_QUERY`. El repo
puede ser público (ej. para mostrarlo en LinkedIn); el endpoint real sigue
siendo privado, requiere un token de Databricks de esta cuenta para invocarse.

`scale_to_zero=True` y `workload_size="Small"`: uso personal de bajo volumen,
no una demo pública con tráfico real -- minimiza cómputo activo contra la
cuota de Model Serving de Free Edition.

Uso:
    uv run python infra/databricks/deploy_agent.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# La consola de Windows por default no maneja bien los emojis que MLflow
# imprime al terminar un run (ej. "🏃 View run..."), y tira
# UnicodeEncodeError con la codepage cp1252 -- visto en vivo (ADR 0015),
# corta el script después de loguear el modelo pero antes de
# registrarlo/desplegarlo.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import mlflow
from mlflow.models.resources import DatabricksServingEndpoint, DatabricksSQLWarehouse

from finhive.config.settings import (
    SQL_WAREHOUSE_ID,
    SUPERVISOR_MODEL_ENDPOINT,
    UC_CATALOG,
    UC_SCHEMA,
    WORKER_MODEL_ENDPOINT,
    get_databricks_host,
)

# Relativo al cwd, no absoluto: `mlflow.pyfunc.log_model(python_model=...)`
# guarda ese path tal cual en los metadatos del modelo ("models from code").
# Con un path absoluto de Windows (`D:\...`), el contenedor de serving en
# Linux intentaba abrir literalmente `/model/D:\...` y fallaba con
# FileNotFoundError -- visto en vivo en los logs del servicio (ADR 0015).
# `.as_posix()` además: `os.path.relpath` en Windows devuelve separadores
# `\`, que en Linux no son separador de path sino un carácter más del
# nombre de archivo -- sin esto, mismo error con otra forma.
# Asume que el script corre desde la raíz del repo, como dice `Uso:` arriba.
_CHAT_AGENT_ABS_PATH = Path(__file__).resolve().parents[2] / "src" / "finhive" / "serving" / "chat_agent.py"
_CHAT_AGENT_PATH = Path(os.path.relpath(_CHAT_AGENT_ABS_PATH, start=os.getcwd())).as_posix()
_MODEL_NAME = f"{UC_CATALOG}.{UC_SCHEMA}.finhive_agent"


def main() -> None:
    from finhive.config.settings import get_databricks_workspace_email

    mlflow.set_tracking_uri("databricks")
    mlflow.set_registry_uri("databricks-uc")
    # Corriendo desde fuera de un notebook no hay experimento implícito --
    # sin esto, mlflow.start_run() falla con "Could not find experiment with
    # ID None" (visto en vivo, ADR 0015). Mismo path que ya usa run_eval.py.
    mlflow.set_experiment(f"/Users/{get_databricks_workspace_email()}/finhive-agent-deploy")

    with mlflow.start_run(run_name="finhive-agent-deploy"):
        logged_model = mlflow.pyfunc.log_model(
            python_model=_CHAT_AGENT_PATH,
            name="agent",
            resources=[
                DatabricksServingEndpoint(endpoint_name=SUPERVISOR_MODEL_ENDPOINT),
                DatabricksServingEndpoint(endpoint_name=WORKER_MODEL_ENDPOINT),
                DatabricksSQLWarehouse(warehouse_id=SQL_WAREHOUSE_ID),
                # AI_GATEWAY_ROUTER_MODEL (workspace.finhive.finhive_router) es
                # un model service de Unity AI Gateway (ADR 0009), no un
                # serving endpoint clásico -- declararlo acá como
                # DatabricksServingEndpoint hizo fallar el deploy en vivo con
                # "NOT_FOUND: Dependent serving endpoint ... does not exist"
                # (ver ADR 0015). mlflow.models.resources no tiene un tipo
                # para model services de AI Gateway todavía. En vez de
                # credential passthrough automático, get_router_chat_model()
                # recibe DATABRICKS_HOST/DATABRICKS_TOKEN vía environment_vars
                # más abajo -- mismo mecanismo manual que ya usa el notebook
                # de demo, con un PAT guardado como secret en vez del token
                # efímero del contexto de notebook (que no existe acá).
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
            "FRED_API_KEY": "{{secrets/finhive/fred_api_key}}",
            "ALPHA_VANTAGE_API_KEY": "{{secrets/finhive/alpha_vantage_api_key}}",
            "TAVILY_API_KEY": "{{secrets/finhive/tavily_api_key}}",
            "SEC_EDGAR_USER_AGENT": "FinHive research-agent matiasadell@hotmail.com",
            "DATABRICKS_HOST": get_databricks_host(),
            "DATABRICKS_TOKEN": "{{secrets/finhive/databricks_token}}",
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

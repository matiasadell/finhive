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

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import mlflow
from mlflow.models.resources import DatabricksServingEndpoint, DatabricksSQLWarehouse

from finhive.config.settings import (
    AI_GATEWAY_ROUTER_MODEL,
    SQL_WAREHOUSE_ID,
    SUPERVISOR_MODEL_ENDPOINT,
    UC_CATALOG,
    UC_SCHEMA,
    WORKER_MODEL_ENDPOINT,
)

_CHAT_AGENT_PATH = str(Path(__file__).resolve().parents[2] / "src" / "finhive" / "serving" / "chat_agent.py")
_MODEL_NAME = f"{UC_CATALOG}.{UC_SCHEMA}.finhive_agent"


def main() -> None:
    mlflow.set_tracking_uri("databricks")
    mlflow.set_registry_uri("databricks-uc")

    with mlflow.start_run(run_name="finhive-agent-deploy"):
        logged_model = mlflow.pyfunc.log_model(
            python_model=_CHAT_AGENT_PATH,
            name="agent",
            resources=[
                DatabricksServingEndpoint(endpoint_name=SUPERVISOR_MODEL_ENDPOINT),
                DatabricksServingEndpoint(endpoint_name=WORKER_MODEL_ENDPOINT),
                # Model service del AI Gateway (ADR 0009), no un serving
                # endpoint clásico -- sin verificar todavía si
                # DatabricksServingEndpoint es el resource type correcto acá
                # (ver ADR 0015). Si el deploy falla por esto, es el primer
                # lugar donde mirar.
                DatabricksServingEndpoint(endpoint_name=AI_GATEWAY_ROUTER_MODEL),
                DatabricksSQLWarehouse(warehouse_id=SQL_WAREHOUSE_ID),
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

# Crea el secret scope `portfolio_intel` (si no existe) y carga los 3 secrets
# teóricos que el resto del código espera ahí, leyéndolos de las mismas env vars
# que hoy usa .env.example -- no imprime ningún valor, solo confirma qué se cargó.
# No se puede correr desde esta máquina (sin conexión a Databricks). Uso:
#   DATABRICKS_HOST=... DATABRICKS_TOKEN=... SQL_WAREHOUSE_ID=... python infra/databricks/setup_secrets.py

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from portfolio_intel.config.settings import SECRET_SCOPE

# (secret key, env var que lo provee localmente)
_SECRETS = [
    ("databricks_host", "DATABRICKS_HOST"),
    ("databricks_token", "DATABRICKS_TOKEN"),
    ("sql_warehouse_id", "SQL_WAREHOUSE_ID"),
]


def main() -> None:
    from databricks.sdk import WorkspaceClient
    from databricks.sdk.errors import ResourceAlreadyExists

    client = WorkspaceClient()

    try:
        client.secrets.create_scope(SECRET_SCOPE)
        print(f"scope creado: {SECRET_SCOPE}")
    except ResourceAlreadyExists:
        print(f"scope ya existía: {SECRET_SCOPE}")

    for key, env_var in _SECRETS:
        value = os.getenv(env_var, "").strip()
        if not value:
            print(f"saltea {key}: {env_var} no está seteada en este entorno.")
            continue
        client.secrets.put_secret(scope=SECRET_SCOPE, key=key, string_value=value)
        print(f"secret cargado: {SECRET_SCOPE}/{key}")


if __name__ == "__main__":
    main()

"""Acceso a los datos del portfolio: interfaz única, dos backends.

Todo lo que está aguas abajo (tools de Task 5-8, agentes, reporte) llama
`load_portfolio_data()` y usa `PortfolioDataStore.get_use_cases()` -- nunca
importa `LocalCSVStore`/`DatabricksDeltaStore` directamente, así que nada
cambia cuando el backend cambia (ver `config.settings.get_data_backend`).

`LocalCSVStore` es lo único que corre en esta máquina de desarrollo (ver
`prompts/constraints_environment.md`). `DatabricksDeltaStore` está escrito
para funcionar de verdad contra Unity Catalog, pero no se puede ejercitar
acá -- se verifica recién en la compu de trabajo.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

import pandas as pd

from portfolio_intel.config.settings import (
    UC_FULL_SCHEMA,
    UC_TABLE_USE_CASE_DETAIL,
    UC_TABLE_USE_CASE_INVENTORY,
    get_data_backend,
    get_sql_warehouse_id,
)
from portfolio_intel.data.schema import DETAIL_JOIN_COLUMN, RUAI_JOIN_COLUMN

_SAMPLE_DOCS_DIR = Path(__file__).resolve().parents[3] / "data" / "sample_docs"


class PortfolioDataStore(ABC):
    """Interfaz común para leer el AI Use Case Inventory, sea cual sea el backend."""

    @abstractmethod
    def get_ruai_inventory(self) -> pd.DataFrame:
        """Devuelve el esquema "RUAI Use Case" tal cual (ver `schema.py`)."""

    @abstractmethod
    def get_use_case_detail(self) -> pd.DataFrame:
        """Devuelve el esquema "AI Use Case Detail" tal cual (ver `schema.py`)."""

    def get_use_cases(self) -> pd.DataFrame:
        """Vista conveniencia: join de ambos esquemas, una fila por caso de uso.

        Implementación por default sobre `get_ruai_inventory`/
        `get_use_case_detail` -- ningún backend necesita sobreescribir esto,
        el join en sí no depende de dónde vinieron los datos.
        """
        ruai = self.get_ruai_inventory()
        detail = self.get_use_case_detail()
        merged = ruai.merge(
            detail,
            left_on=RUAI_JOIN_COLUMN,
            right_on=DETAIL_JOIN_COLUMN,
            how="inner",
            validate="one_to_one",
        )
        orphans_ruai = set(ruai[RUAI_JOIN_COLUMN]) - set(detail[DETAIL_JOIN_COLUMN])
        orphans_detail = set(detail[DETAIL_JOIN_COLUMN]) - set(ruai[RUAI_JOIN_COLUMN])
        if orphans_ruai or orphans_detail:
            raise ValueError(
                "El join entre RUAI Use Case y AI Use Case Detail dejó filas "
                f"huérfanas -- solo en RUAI: {orphans_ruai or 'ninguna'}; solo "
                f"en Detail: {orphans_detail or 'ninguna'}. Los títulos tienen "
                "que matchear exactamente entre los dos archivos."
            )
        return merged


class LocalCSVStore(PortfolioDataStore):
    """Lee los dos CSVs sintéticos de `data/sample_docs/` vía pandas.

    Es el backend usado en toda esta máquina de desarrollo -- ver
    `data/sample_docs/README.md` para cómo (re)generarlos.
    """

    def __init__(self, sample_docs_dir: Path | None = None) -> None:
        self._dir = sample_docs_dir or _SAMPLE_DOCS_DIR

    def get_ruai_inventory(self) -> pd.DataFrame:
        path = self._dir / "rua_use_case_inventory.csv"
        if not path.exists():
            raise FileNotFoundError(
                f"{path} no existe -- corré `python -m portfolio_intel.data.synthetic` "
                "desde la raíz del repo para generarlo (ver data/sample_docs/README.md)."
            )
        return pd.read_csv(path)

    def get_use_case_detail(self) -> pd.DataFrame:
        path = self._dir / "ai_use_case_detail.csv"
        if not path.exists():
            raise FileNotFoundError(
                f"{path} no existe -- corré `python -m portfolio_intel.data.synthetic` "
                "desde la raíz del repo para generarlo (ver data/sample_docs/README.md)."
            )
        return pd.read_csv(path)


class DatabricksDeltaStore(PortfolioDataStore):
    """Lee las tablas Delta reales de `workspace.portfolio_intel` en Unity Catalog.

    Mismo patrón que `execute_sql` de finhive (`memory/store.py`, hoy
    archivado en `finhive-legacy`): Statement Execution API contra el SQL
    warehouse serverless, autenticado vía `databricks.sdk.WorkspaceClient`
    (OAuth ambiente, `DATABRICKS_CONFIG_PROFILE`). No se puede ejercitar
    desde esta máquina de desarrollo -- ver
    `prompts/constraints_environment.md`. Las dos tablas
    (`UC_TABLE_USE_CASE_INVENTORY`, `UC_TABLE_USE_CASE_DETAIL`) todavía no
    están provisionadas en ningún workspace real; provisionarlas (DDL +
    carga desde los CSVs) es trabajo de infra futuro, fuera de alcance de
    este pase (ver `prompts/non_goals.md`).
    """

    def __init__(self, warehouse_id: str | None = None) -> None:
        self._warehouse_id = warehouse_id or get_sql_warehouse_id()

    def _execute_sql(self, statement: str) -> pd.DataFrame:
        from databricks.sdk import WorkspaceClient
        from databricks.sdk.service.sql import StatementState

        client = WorkspaceClient()
        response = client.statement_execution.execute_statement(
            statement=statement,
            warehouse_id=self._warehouse_id,
            wait_timeout="30s",
        )
        if response.status and response.status.state == StatementState.FAILED:
            raise RuntimeError(f"statement SQL falló: {response.status.error}")

        columns = [c.name for c in response.manifest.schema.columns] if response.manifest else []
        rows = response.result.data_array if response.result and response.result.data_array else []
        return pd.DataFrame(rows, columns=columns)

    def get_ruai_inventory(self) -> pd.DataFrame:
        return self._execute_sql(f"SELECT * FROM {UC_FULL_SCHEMA}.{UC_TABLE_USE_CASE_INVENTORY}")

    def get_use_case_detail(self) -> pd.DataFrame:
        return self._execute_sql(f"SELECT * FROM {UC_FULL_SCHEMA}.{UC_TABLE_USE_CASE_DETAIL}")


def load_portfolio_data() -> PortfolioDataStore:
    """Factory: devuelve el backend correcto según `get_data_backend()`.

    Todo el resto del sistema llama a esto, nunca instancia
    `LocalCSVStore`/`DatabricksDeltaStore` directamente -- mismo criterio de
    centralización que `config.settings.get_chat_model`.
    """
    backend = get_data_backend()
    if backend == "local":
        return LocalCSVStore()
    return DatabricksDeltaStore()

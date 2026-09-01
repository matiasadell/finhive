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
    @abstractmethod
    def get_ruai_inventory(self) -> pd.DataFrame: ...

    @abstractmethod
    def get_use_case_detail(self) -> pd.DataFrame: ...

    def get_use_cases(self) -> pd.DataFrame:
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

        schema_columns = response.manifest.schema.columns if response.manifest else []
        columns = [c.name for c in schema_columns]
        rows = response.result.data_array if response.result and response.result.data_array else []
        df = pd.DataFrame(rows, columns=columns)

        # data_array siempre llega como strings -- castear según el tipo
        # real de la columna Delta, si no las cuentas numéricas de tools/*.py rompen.
        for col in schema_columns:
            type_name = str(col.type_name.value if hasattr(col.type_name, "value") else col.type_name)
            if type_name in ("INT", "BIGINT", "SMALLINT", "TINYINT", "DOUBLE", "FLOAT", "DECIMAL"):
                df[col.name] = pd.to_numeric(df[col.name], errors="coerce")
            elif type_name in ("DATE", "TIMESTAMP"):
                df[col.name] = pd.to_datetime(df[col.name], errors="coerce")
        return df

    def get_ruai_inventory(self) -> pd.DataFrame:
        return self._execute_sql(f"SELECT * FROM {UC_FULL_SCHEMA}.{UC_TABLE_USE_CASE_INVENTORY}")

    def get_use_case_detail(self) -> pd.DataFrame:
        return self._execute_sql(f"SELECT * FROM {UC_FULL_SCHEMA}.{UC_TABLE_USE_CASE_DETAIL}")


def load_portfolio_data() -> PortfolioDataStore:
    backend = get_data_backend()
    if backend == "local":
        return LocalCSVStore()
    return DatabricksDeltaStore()

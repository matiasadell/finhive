"""Crea el índice de Vector Search sobre 10-K de SEC EDGAR (idempotente, ver ADR 0017).

Alcance chico a propósito: último 10-K de AAPL y MSFT solamente (prueba de
concepto de RAG narrativo, no un pipeline de ingesta general). Índice Delta
Sync (`pipeline_type="TRIGGERED"`, mismo criterio de costo que
`scale_to_zero` en ADR 0015): Databricks calcula los embeddings solo contra
`EMBEDDING_ENDPOINT`, sin llamar a un endpoint de embeddings a mano.

Uso:
    uv run python infra/databricks/setup_vector_search.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from finhive.config.settings import (
    EMBEDDING_ENDPOINT,
    EQUITY_FILINGS_INDEX,
    UC_FULL_SCHEMA,
    VECTOR_SEARCH_ENDPOINT,
    get_databricks_host,
    get_databricks_token,
)
from finhive.memory.store import execute_sql
from finhive.rag.ingest import chunk_text, fetch_filing_text

_TABLE = f"{UC_FULL_SCHEMA}.equity_filing_chunks"
_TICKERS = ["AAPL", "MSFT"]
_INSERT_BATCH_SIZE = 50

_CREATE_TABLE = f"""
CREATE TABLE IF NOT EXISTS {_TABLE} (
    chunk_id STRING,
    ticker STRING,
    form_type STRING,
    accession_number STRING,
    filing_date STRING,
    chunk_index INT,
    chunk_text STRING
)
TBLPROPERTIES (delta.enableChangeDataFeed = true)
"""


def _sql_escape(value: str) -> str:
    return value.replace("'", "''")


def _ticker_already_ingested(ticker: str) -> bool:
    rows = execute_sql(f"SELECT COUNT(*) FROM {_TABLE} WHERE ticker = :ticker", params={"ticker": ticker})
    return bool(rows) and int(rows[0][0]) > 0


def _ingest_ticker(ticker: str) -> int:
    """Descarga, trocea e inserta el último 10-K de un ticker. Devuelve la cantidad de chunks."""
    filing = fetch_filing_text(ticker, "10-K")
    chunks = chunk_text(filing["text"])

    for batch_start in range(0, len(chunks), _INSERT_BATCH_SIZE):
        batch = chunks[batch_start : batch_start + _INSERT_BATCH_SIZE]
        values = []
        for offset, chunk in enumerate(batch):
            chunk_index = batch_start + offset
            chunk_id = f"{ticker}_{filing['accession_number']}_{chunk_index}"
            values.append(
                "("
                f"'{_sql_escape(chunk_id)}', "
                f"'{_sql_escape(ticker)}', "
                f"'{_sql_escape(filing['form_type'])}', "
                f"'{_sql_escape(filing['accession_number'])}', "
                f"'{_sql_escape(filing['filing_date'])}', "
                f"{chunk_index}, "
                f"'{_sql_escape(chunk)}'"
                ")"
            )
        execute_sql(
            f"INSERT INTO {_TABLE} "
            "(chunk_id, ticker, form_type, accession_number, filing_date, chunk_index, chunk_text) "
            "VALUES " + ", ".join(values)
        )
    return len(chunks)


def main() -> None:
    from databricks.ai_search.client import VectorSearchClient

    execute_sql(_CREATE_TABLE)
    print(f"tabla lista: {_TABLE}")

    for ticker in _TICKERS:
        if _ticker_already_ingested(ticker):
            print(f"{ticker}: ya ingerido, se omite")
            continue
        num_chunks = _ingest_ticker(ticker)
        print(f"{ticker}: {num_chunks} chunks insertados")

    # VectorSearchClient no soporta OAuth ambiente (`databricks-cli` profile,
    # el mismo que usa `WorkspaceClient()` sin argumentos en el resto del
    # proyecto) -- solo PAT, service principal o auto-detección de notebook.
    # Reusa DATABRICKS_HOST/DATABRICKS_TOKEN, el mismo PAT que ya usa
    # `get_router_chat_model()` para el AI Gateway.
    client = VectorSearchClient(
        workspace_url=get_databricks_host(),
        personal_access_token=get_databricks_token(),
        disable_notice=True,
    )

    if not client.endpoint_exists(VECTOR_SEARCH_ENDPOINT):
        client.create_endpoint_and_wait(name=VECTOR_SEARCH_ENDPOINT, endpoint_type="STANDARD")
        print(f"endpoint creado: {VECTOR_SEARCH_ENDPOINT}")
    else:
        print(f"endpoint ya existe: {VECTOR_SEARCH_ENDPOINT}")

    if not client.index_exists(endpoint_name=VECTOR_SEARCH_ENDPOINT, index_name=EQUITY_FILINGS_INDEX):
        client.create_delta_sync_index_and_wait(
            endpoint_name=VECTOR_SEARCH_ENDPOINT,
            index_name=EQUITY_FILINGS_INDEX,
            primary_key="chunk_id",
            source_table_name=_TABLE,
            pipeline_type="TRIGGERED",
            embedding_model_endpoint_name=EMBEDDING_ENDPOINT,
            embedding_source_column="chunk_text",
            columns_to_sync=["ticker", "form_type", "filing_date", "chunk_text"],
        )
        print(f"índice creado y sincronizado: {EQUITY_FILINGS_INDEX}")
    else:
        index = client.get_index(endpoint_name=VECTOR_SEARCH_ENDPOINT, index_name=EQUITY_FILINGS_INDEX)
        index.sync()
        print(f"índice ya existía, resincronizado: {EQUITY_FILINGS_INDEX}")


if __name__ == "__main__":
    main()

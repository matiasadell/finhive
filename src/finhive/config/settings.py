"""Configuración central: endpoints de modelo, Unity Catalog, y factory de LLM.

Todos los dominios (macro, equity, portfolio_risk, news_sentiment, crypto_alt)
importan `get_chat_model` desde acá en vez de instanciar `ChatDatabricks`
directamente, para que el tiering de modelos (supervisor vs worker) sea una
única decisión centralizada.
"""

from __future__ import annotations

import os
from typing import Literal

from dotenv import load_dotenv

load_dotenv()

# --- Unity Catalog ---
UC_CATALOG = "workspace"
UC_SCHEMA = "finhive"
UC_FULL_SCHEMA = f"{UC_CATALOG}.{UC_SCHEMA}"

# --- Foundation Model APIs nativos de Databricks (ver ADR 0003) ---
SUPERVISOR_MODEL_ENDPOINT = "databricks-meta-llama-3-3-70b-instruct"
WORKER_MODEL_ENDPOINT = "databricks-meta-llama-3-1-8b-instruct"
EMBEDDING_ENDPOINT = "databricks-gte-large-en"


def get_fred_api_key() -> str:
    """Lee FRED_API_KEY de env; falla explícito si no está configurada."""
    key = os.getenv("FRED_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "FRED_API_KEY no está seteada. Conseguila gratis en "
            "https://fred.stlouisfed.org/docs/api/api_key.html y ponela en tu .env."
        )
    return key


def get_sec_edgar_user_agent() -> str:
    """Lee SEC_EDGAR_USER_AGENT de env; falla explícito si no está configurada.

    SEC EDGAR no requiere API key, pero exige un User-Agent descriptivo con
    contacto real (su fair access policy bloquea requests sin esto).
    """
    ua = os.getenv("SEC_EDGAR_USER_AGENT", "").strip()
    if not ua:
        raise RuntimeError(
            "SEC_EDGAR_USER_AGENT no está seteada. Poné algo como "
            '"TuNombre tu-email@ejemplo.com" en tu .env — SEC EDGAR exige un '
            "User-Agent descriptivo, aunque no pide API key."
        )
    return ua


def get_alpha_vantage_api_key() -> str:
    """Lee ALPHA_VANTAGE_API_KEY de env; falla explícito si no está configurada.

    Ojo: el free tier de Alpha Vantage es chico (históricamente ~25
    requests/día) — usar con cuidado en tests/desarrollo, no en loops.
    """
    key = os.getenv("ALPHA_VANTAGE_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "ALPHA_VANTAGE_API_KEY no está seteada. Conseguila gratis en "
            "https://www.alphavantage.co/support/#api-key y ponela en tu .env."
        )
    return key


def get_tavily_api_key() -> str:
    """Lee TAVILY_API_KEY de env; falla explícito si no está configurada."""
    key = os.getenv("TAVILY_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "TAVILY_API_KEY no está seteada. Conseguila gratis en "
            "https://tavily.com y ponela en tu .env."
        )
    return key


def get_chat_model(tier: Literal["supervisor", "worker"], temperature: float = 0.1):
    """Instancia un `ChatDatabricks` apuntando al endpoint correcto según el rol.

    Args:
        tier: "supervisor" para supervisores de dominio y el top-level supervisor
            (routing y síntesis, requieren más capacidad de razonamiento);
            "worker" para agentes hoja que solo hacen tool calling/extracción.
        temperature: temperatura de muestreo, baja por default para respuestas
            consistentes en un dominio financiero.
    """
    from databricks_langchain import ChatDatabricks

    endpoint = SUPERVISOR_MODEL_ENDPOINT if tier == "supervisor" else WORKER_MODEL_ENDPOINT
    return ChatDatabricks(endpoint=endpoint, temperature=temperature)

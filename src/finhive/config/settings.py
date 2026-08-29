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

# --- Unity AI Gateway: model services con routing real (ver ADR 0009) ---
# A diferencia de los endpoints de arriba (servidos vía ChatDatabricks, path
# clásico /serving-endpoints/), estos son "model services" de Unity Catalog,
# consumidos vía el cliente OpenAI-compatible contra /ai-gateway/mlflow/v1.
AI_GATEWAY_ROUTER_MODEL = "workspace.finhive.finhive_router"
AI_GATEWAY_EMBEDDINGS_MODEL = "workspace.finhive.finhive_embeddings"


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


def get_databricks_host() -> str:
    """Lee DATABRICKS_HOST de env; falla explícito si no está configurada."""
    host = os.getenv("DATABRICKS_HOST", "").strip()
    if not host:
        raise RuntimeError(
            "DATABRICKS_HOST no está seteada. Es la URL de tu workspace "
            "(ej. https://dbc-xxxxxxxx-xxxx.cloud.databricks.com), necesaria "
            "para el cliente OpenAI-compatible contra AI Gateway."
        )
    return host


def get_databricks_token() -> str:
    """Lee DATABRICKS_TOKEN de env; falla explícito si no está configurada.

    A diferencia del resto del proyecto (que usa OAuth vía
    DATABRICKS_CONFIG_PROFILE, sin token estático), el cliente OpenAI-
    compatible de AI Gateway necesita un Bearer token fijo — un Personal
    Access Token de Databricks. Generar uno con
    `databricks tokens create --lifetime-seconds <segundos>` y guardarlo acá,
    nunca en texto plano en ningún otro lado.
    """
    token = os.getenv("DATABRICKS_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "DATABRICKS_TOKEN no está seteada. Generá un Personal Access "
            "Token con `databricks tokens create` y ponelo en tu .env — lo "
            "necesita el cliente OpenAI-compatible contra AI Gateway."
        )
    return token


def get_router_chat_model(temperature: float = 0.1):
    """Instancia un `ChatOpenAI` apuntando al model service con routing real.

    A diferencia de `get_chat_model`, que pega directo a un único endpoint
    de Databricks vía `ChatDatabricks`, esto pasa por el Unity AI Gateway
    (`/ai-gateway/mlflow/v1`) y el tráfico se reparte según la config de
    `AI_GATEWAY_ROUTER_MODEL` (hoy: 70% Llama 3.3 70B / 30% GPT OSS 120B —
    ver ADR 0009). Usado por el top-level supervisor, el nodo más crítico
    del sistema, para que se beneficie de resiliencia real a la degradación
    de un único modelo.
    """
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=AI_GATEWAY_ROUTER_MODEL,
        openai_api_key=get_databricks_token(),
        openai_api_base=f"{get_databricks_host()}/ai-gateway/mlflow/v1",
        temperature=temperature,
    )


def get_gateway_embeddings():
    """Instancia un `OpenAIEmbeddings` apuntando al model service de embeddings.

    Igual que `get_router_chat_model`, pasa por Unity AI Gateway en vez de
    pegarle directo al serving endpoint — mismo gobierno (rate limits,
    tracking) que el resto de los model services. Todavía no está en uso
    activo (Vector Search de FinHive no tiene índice creado aún), pero deja
    lista la conexión para cuando se implemente RAG.
    """
    from langchain_openai import OpenAIEmbeddings

    return OpenAIEmbeddings(
        model=AI_GATEWAY_EMBEDDINGS_MODEL,
        openai_api_key=get_databricks_token(),
        openai_api_base=f"{get_databricks_host()}/ai-gateway/mlflow/v1",
        # Sin esto, OpenAIEmbeddings pre-tokeniza (con tiktoken o, si eso se
        # desactiva, con transformers) asumiendo un modelo real de OpenAI, y
        # manda arrays de token IDs en vez de texto plano -- AI Gateway lo
        # rechaza con 400 BAD_REQUEST para un modelo que no es de OpenAI
        # (acá, GTE Large de Databricks). check_embedding_ctx_length=False
        # salta ese codepath entero y manda el string tal cual.
        check_embedding_ctx_length=False,
    )


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

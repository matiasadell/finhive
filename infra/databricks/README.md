# infra/databricks/

Scripts de infraestructura (Python + `databricks-sdk`, no Terraform ni Asset Bundles —
el flujo de dev elegido es Databricks Repos + notebooks nativos) para dejar el workspace
listo antes de correr el pipeline de agentes.

Roadmap (fase de implementación, todavía no escrito):

- `setup_catalog.py` — crea/valida el schema `workspace.finhive` y el volume
  `workspace.finhive.docs`, idempotente (ver "Estado actual" abajo, ya provisionado).
- `setup_vector_search.py` — crea el índice consolidado sobre `finhive_vs_endpoint`
  (con columna `domain` para filtrar por macro/equity/news/crypto/portfolio).
- `setup_secrets.py` — carga secrets al scope `finhive`; nunca imprime valores, lee
  desde un archivo local no trackeado o pide input interactivo vía la CLI.

**`register_uc_functions.py`** (ya escrito, no es roadmap) — registra funciones Python
como Unity Catalog Functions, genérico y reutilizable entre dominios. Es el reemplazo de
los Managed MCP servers de Databricks (que facturan cómputo serverless por invocación) —
ver ADR 0004. Uso: `uv run python infra/databricks/register_uc_functions.py`.

El LLM **no requiere registrar un External Model**: se usan los Foundation Model APIs
nativos de Databricks (`system.ai.*`), ya provisionados en el workspace y gratis en Free
Edition — ver ADR 0003. Se evaluó Groq como External Model tipo `custom` (ADR 0002) pero
se descartó a favor de los modelos nativos: cero setup adicional, cero dependencia de key
externa, mismo nivel de gobernanza vía AI Gateway.

## Estado actual (infraestructura ya provisionada y verificada en vivo)

| Recurso | Nombre | Notas |
|---|---|---|
| Catalog | `workspace` (existente) | Free Edition no permite crear catalogs nuevos vía CLI sin un storage root pre-provisionado por la UI (Default Storage); se usa el catalog `workspace` ya existente en vez de uno dedicado |
| Schema | `workspace.finhive` | Namespace del proyecto dentro del catalog |
| Volume | `workspace.finhive.docs` | Managed volume para el corpus crudo del RAG |
| Vector Search endpoint | `finhive_vs_endpoint` | Tipo `STANDARD`, estado `ONLINE`. Sin índices todavía — se crean junto con la ingesta real |
| Secret scope | `finhive` | `fred_api_key`, `alpha_vantage_api_key`, `tavily_api_key` cargados — usados por `notebooks/00_demo.py` vía `dbutils.secrets` |
| LLM — supervisores | `databricks-meta-llama-3-3-70b-instruct` (`system.ai.llama_v3_3_70b_instruct`) | `READY`. AI Gateway: rate limit 30 calls/usuario/min (ADR 0008) |
| LLM — workers | `databricks-meta-llama-3-1-8b-instruct` (`system.ai.meta_llama_v3_1_8b_instruct`) | `READY`. AI Gateway: rate limit 60 calls/usuario/min (ADR 0008) |
| Embeddings — Vector Search | `databricks-gte-large-en` (`system.ai.gte_large_en_v1_5`) | `READY`. AI Gateway: rate limit 60 calls/usuario/min (ADR 0008) |
| UC Functions (Macro) | `search_fred_series`, `get_fred_series_latest`, `get_fred_series_history` | Registradas y gobernadas en UC; ejecución real en proceso propio, no vía `UCFunctionToolkit` (ver ADR 0004) |
| UC Functions (Equity) | `get_stock_quote`, `get_stock_fundamentals`, `get_stock_price_history`, `calculate_sma`, `search_sec_filings`, `get_sec_company_facts` | Ídem, registradas en `workspace.finhive` |
| UC Functions (Portfolio & Risk) | `calculate_portfolio_volatility`, `calculate_portfolio_var`, `calculate_correlation_matrix`, `calculate_sharpe_ratio`, `add_numbers`, `multiply_numbers`, `divide_numbers` | Ídem — cómputo propio con numpy/pandas, no solo passthrough a una API |
| UC Functions (News & Sentiment) | `get_stock_news_sentiment`, `get_market_news_sentiment`, `get_earnings_calendar`, `web_search_news` | Ídem — Alpha Vantage (sentiment/calendario) + Tavily (fallback web estilo CRAG) |
| UC Functions (Crypto & Alt) | `search_crypto_id`, `get_crypto_price`, `get_crypto_price_history`, `get_trending_crypto`, `get_top_crypto_by_market_cap` | Ídem — CoinGecko, API pública sin key |

25 UC Functions registradas en total, los 5 dominios completos. Todas las tools de los 5
dominios están envueltas con `finhive.tools.wrappers.safe_tool` (ADR 0007): errores de
red/rate-limit se devuelven como observación al LLM en vez de crashear el grafo.

Los 3 endpoints de FinHive tienen `usage_tracking_config` **y** `rate_limits` explícitos
de AI Gateway (ADR 0008) — no solo el tracking default que Databricks aplica sin pedirlo.

Ver `docs/architecture/adr/` (0001-0008) para el historial completo de estas decisiones.

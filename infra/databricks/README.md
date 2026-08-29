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
| Secret scope | `finhive` | Creado, vacío (sin secrets del LLM cargados, ya no hace falta) |
| LLM — supervisores | `databricks-meta-llama-3-3-70b-instruct` (`system.ai.llama_v3_3_70b_instruct`) | Query de prueba exitosa vía CLI, sin costo |
| LLM — workers | `databricks-meta-llama-3-1-8b-instruct` (`system.ai.meta_llama_v3_1_8b_instruct`) | Ya `READY` |
| Embeddings — Vector Search | `databricks-gte-large-en` (`system.ai.gte_large_en_v1_5`) | Ya `READY` |
| UC Functions (dominio Macro) | `workspace.finhive.search_fred_series`, `.get_fred_series_latest`, `.get_fred_series_history` | Registradas y gobernadas en UC; ejecución real en proceso propio, no vía `UCFunctionToolkit` (ver ADR 0004) |

Ver `docs/architecture/adr/` (0001-0004) para el historial completo de estas decisiones.

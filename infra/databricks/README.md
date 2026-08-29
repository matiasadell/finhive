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
- `register_external_model.py` — registra Groq (provider `custom`, API OpenAI-compatible
  en `https://api.groq.com/openai/v1`) como External Model en Databricks Model Serving,
  gobernado por AI Gateway. Ver ADR 0002 (`docs/architecture/adr/`).

## Estado actual (infraestructura mínima ya provisionada)

| Recurso | Nombre | Notas |
|---|---|---|
| Catalog | `workspace` (existente) | Free Edition no permite crear catalogs nuevos vía CLI sin un storage root pre-provisionado por la UI (Default Storage); se usa el catalog `workspace` ya existente en vez de uno dedicado |
| Schema | `workspace.finhive` | Namespace del proyecto dentro del catalog |
| Volume | `workspace.finhive.docs` | Managed volume para el corpus crudo del RAG |
| Vector Search endpoint | `finhive_vs_endpoint` | Tipo `STANDARD`, estado `ONLINE`. Sin índices todavía — se crean junto con la ingesta real |
| Secret scope | `finhive` | Creado vacío; los valores se cargan con `databricks secrets put-secret` cuando el usuario tenga cada key, nunca pegados en un chat |

Ver `docs/architecture/adr/0001-arquitectura-inicial.md` para el detalle de por qué se
usó `workspace.finhive` en vez de un catalog `finhive` dedicado.

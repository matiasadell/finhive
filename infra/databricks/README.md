# infra/databricks/

Scripts de infraestructura (Python + `databricks-sdk`, no Terraform ni Asset Bundles —
el flujo de dev elegido es Databricks Repos + notebooks nativos) para dejar el workspace
listo antes de correr el pipeline de agentes.

Roadmap (fase de implementación, todavía no escrito):

- `setup_catalog.py` — crea el catalog `finhive` y los schemas `raw`/`agents`, idempotente.
- `setup_vector_search.py` — crea el endpoint único de Vector Search y el índice
  consolidado (con columna `domain` para filtrar por macro/equity/news/crypto/portfolio).
- `setup_secrets.py` — crea el secret scope de Databricks; nunca imprime valores, lee
  desde un archivo local no trackeado o pide input interactivo vía la CLI.
- `register_external_model.py` — registra Claude (Anthropic) como External Model en
  Databricks Model Serving, gobernado por AI Gateway.

El estado de la infraestructura mínima (catalog/schema/volume base) se documenta en
`docs/architecture/adr/0001-arquitectura-inicial.md`.

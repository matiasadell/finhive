# notebooks/

Notebooks de Databricks (sincronizados vía Databricks Repos → GitHub), pensados como
orquestadores finos que importan la lógica real desde `src/finhive/` — no contienen
lógica de negocio propia, solo ensamblan y ejecutan.

Roadmap (fase de implementación, todavía no escrito):

| Notebook | Propósito |
|---|---|
| `00_setup_unity_catalog.py` | Crea catalog/schema/volumes si no existen (idempotente) |
| `01_ingest_macro_docs.py` | Ingesta de datos macro (FRED) al corpus RAG |
| `02_ingest_equity_filings.py` | Ingesta de 10-K/10-Q (SEC EDGAR) + construcción del árbol RAPTOR |
| `03_build_vector_search_index.py` | Sincroniza el índice único de Databricks Vector Search |
| `04_run_agent_graph.py` | Invoca el grafo jerárquico completo con una query de prueba |
| `05_evaluate_agents.py` | Corre la suite de evaluación (`mlflow.genai.evaluate`) |

# data/sample_docs/

Un puñado de documentos pequeños (algún 10-K recortado, un par de comunicados de la Fed)
para smoke-tests locales del pipeline de RAG, sin depender de la red ni de Databricks.

El corpus real (10-Ks completos, históricos de FRED, noticias) **no vive en este repo**:
se ingesta directamente a Unity Catalog Volumes desde las fuentes (SEC EDGAR, FRED,
Alpha Vantage) vía los notebooks de `notebooks/`. `.gitignore` excluye todo `data/`
salvo esta carpeta, para que el repo no crezca con corpora grandes.

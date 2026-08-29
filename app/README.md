# app/

Demo desplegada como [Databricks App](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/)
(Streamlit), consumida directamente por `src/finhive` para invocar el grafo de agentes.

Roadmap (fase de implementación, todavía no escrito):

- `app.py` — UI de Streamlit: chat con el supervisor raíz, visualización de qué
  sub-supervisor/worker respondió, trazas de MLflow embebidas.
- `app.yaml` — manifiesto de despliegue de Databricks Apps (comando de arranque, env vars).
- `requirements.txt` — dependencias mínimas del runtime de la app (subset de `pyproject.toml`).

Se despliega con `databricks apps deploy` una vez que `src/finhive` tenga el grafo armado.

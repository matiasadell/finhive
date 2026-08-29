# tests/

- `unit/` — funciones puras y testeables sin llamadas a LLM/red: guardrails de tópico,
  grading de retrieval (CRAG), cálculos de riesgo/portfolio, parsing de datos.
- `integration/` — pruebas de extremo a extremo del grafo de agentes contra un LLM real
  (Claude vía AI Gateway); requieren `.env` completo y corren aparte del suite rápido.

Se corren con `pytest` (config en `pyproject.toml`). Todavía no hay tests porque todavía
no hay lógica de agentes — se agregan junto con cada módulo, no después.

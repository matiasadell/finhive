# tests/

- `integration/` — único suite que existe hoy: pruebas de extremo a extremo del grafo de
  agentes contra Databricks real (Foundation Model APIs nativos + Unity AI Gateway) y las
  APIs de datos reales (FRED, yfinance, SEC EDGAR, Alpha Vantage, CoinGecko). Requieren
  `.env` completo y la CLI de Databricks autenticada; no corren en CI, se corren a mano
  (marcador `integration` en `pyproject.toml`, sujeto a rate limiting de cuota del Free
  Edition si se corren varios seguidos).

Un `unit/` para funciones puras (cálculos de riesgo/portfolio, parsing) quedó descartado
por ahora — todo el código no trivial del proyecto termina invocando un LLM (guardrails
incluidos: son nodos con `with_structured_output`, no reglas hardcodeadas) o una API
externa, así que separar "unit" de "integration" hubiera dejado ese suite casi vacío.

Se corren con `pytest` (config en `pyproject.toml`):

```bash
uv run pytest tests/integration -v -s
```

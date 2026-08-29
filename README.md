# FinHive

Sistema multiagente **jerárquico** de análisis financiero: un supervisor raíz coordina
cinco sub-supervisores especializados por dominio (macro, equity, portfolio/risk,
news/sentiment, crypto), cada uno con sus propios workers — construido sobre LangGraph
y desplegado sobre Databricks (Unity Catalog, Vector Search, Model Serving/AI Gateway,
Databricks Apps).

> ⚠️ **Este proyecto es una herramienta de research/análisis, no asesoramiento financiero
> ni ejecución de trades reales.** Ver guardrails y disclaimers en `src/finhive/guardrails/`.

> 🚧 **Estado**: en construcción. Este README describe la arquitectura objetivo; el
> checklist de abajo indica qué está implementado hoy.

## Arquitectura

```
                         Top-Level Supervisor (Llama 3.3 70B nativo, vía AI Gateway)
                         router de complejidad: trivial / single- / multi-domain
                                          │
        ┌───────────┬──────────────┬─────┴────────┬──────────────┬───────────┐
        ▼           ▼              ▼               ▼              ▼
     Macro      Equity Research  Portfolio &     News &        Crypto &
   Supervisor    Supervisor      Risk Superv.   Sentiment Sup.  Alt Assets Sup.
```

Cada worker sigue el patrón ReAct; cada sub-supervisor compone sus workers como un
sub-grafo de LangGraph; el supervisor raíz compone los cinco sub-grafos ("Hierarchical
Agent Teams"). El detalle completo de decisiones de arquitectura está en
[`docs/architecture/adr/`](docs/architecture/adr/) (ADRs 0001-0005), incluyendo un mapa
explícito de qué concepto de arquitectura agéntica (ReAct, Reflexion, Self-RAG/CRAG,
RAPTOR, Adaptive-RAG, Mixture-of-Agents, MCP, LLM Gateway, etc.) se aplica en qué parte
del sistema — MCP, por ejemplo, se resuelve como Unity Catalog Functions gobernadas
(ADR 0004), no como los Managed MCP servers de Databricks (que facturan por invocación).
El supervisor raíz ya compone equipos de dominio de verdad (ADR 0005), con un límite duro
de iteraciones como salvaguarda de cuota.

Este proyecto nació de una investigación teórica propia sobre arquitecturas agénticas —
ver [`docs/theory/main.pdf`](docs/theory/main.pdf) (timeline de 24 arquitecturas, 2020-2026)
y [`docs/theory/Summary.pdf`](docs/theory/Summary.pdf) (resumen conceptual de RAG y agentes) —
implementada acá sobre un caso de uso financiero real.

## Stack

| Capa | Tecnología |
|---|---|
| Orquestación de agentes | LangGraph (+ `langgraph-supervisor`) |
| LLM | Foundation Model APIs nativos de Databricks (Llama 3.3 70B / Llama 3.1 8B), gratis en Free Edition, gobernados por AI Gateway |
| Gateway / gobernanza | Databricks AI Gateway |
| Vector search | Databricks Vector Search sobre Unity Catalog (embeddings: GTE Large nativo de Databricks) |
| Almacenamiento / catálogo | Unity Catalog (tablas, volumes) |
| Memoria persistente | Lakebase (Postgres serverless) |
| Observabilidad / evaluación | MLflow Tracing + MLflow Evaluate, LangSmith |
| Demo | Streamlit, desplegado como Databricks App |
| Datos financieros | yfinance, SEC EDGAR, FRED, Alpha Vantage, CoinGecko, Tavily |

## Estructura del repo

```
src/finhive/       paquete Python: agentes, tools, RAG, guardrails, memoria, evaluación
notebooks/         notebooks de Databricks (Repos), orquestan sobre src/finhive
app/                demo Streamlit desplegada como Databricks App
infra/databricks/  scripts de setup del workspace (catalog, vector search, secrets)
docs/               teoría de base, ADRs de arquitectura, artículo técnico final
tests/              unit + integration
data/sample_docs/  corpus mínimo para smoke-tests locales (el corpus real vive en UC Volumes)
```

## Quickstart (desarrollo local)

```bash
uv sync                        # instala dependencias (ver pyproject.toml)
cp .env.example .env           # completar con tus propias keys (nunca commitear .env)
databricks auth login --host <tu-workspace-url>   # OAuth, no pega ningún token en texto
```

Ver `.env.example` para la lista completa de cuentas/API keys necesarias y dónde
obtenerlas (todas gratuitas o free-tier).

## Roadmap

- [x] Diseño de arquitectura y ADR
- [x] Estructura de repo
- [x] Infraestructura mínima de Databricks (schema, volume, vector search endpoint, secret scope)
- [x] LLM: Foundation Model APIs nativos de Databricks verificados en vivo (Llama 3.3 70B / 3.1 8B), sin key externa
- [x] Sub-supervisor de Macro (3 workers ReAct + supervisor, tools sobre FRED registradas en Unity Catalog)
- [x] Top-level supervisor + composición jerárquica (Macro + Equity, verificado end-to-end)
- [x] Sub-supervisor de Equity Research (fundamentals/técnico/filings, tools sobre yfinance + SEC EDGAR)
- [ ] Sub-supervisor de Portfolio & Risk
- [ ] Sub-supervisor de News & Sentiment
- [ ] Sub-supervisor de Crypto & Alt
- [ ] Guardrails y memoria persistente
- [ ] Evaluación (MLflow + LangSmith)
- [ ] Demo Streamlit desplegada
- [ ] Artículo técnico (`docs/writeup/`)

## Autor

Matías Adell — [main.pdf](docs/theory/main.pdf) y [Summary.pdf](docs/theory/Summary.pdf)
son investigación propia sobre arquitecturas agénticas que fundamentan las decisiones de
diseño de este proyecto.

## Licencia

MIT — ver [LICENSE](LICENSE).

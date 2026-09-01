# Portfolio Intel

**AI Portfolio Intelligence Agent** — un sistema multiagente jerárquico que ayuda a
leadership a tomar mejores decisiones de inversión en el portfolio de casos de uso de IA
de la empresa: qué priorizar, qué es duplicado/reusable, qué no está realizando el valor
prometido, y dónde escalar, consolidar, reducir o discontinuar inversión — construido
sobre LangGraph, pensado para correr contra Databricks (Foundation Model APIs nativos +
Unity Catalog).

> Este proyecto es una capa de inteligencia/decision-support que **complementa** el
> proceso existente de AI Intake, aprobación y governance de la empresa — no lo
> reemplaza, y no ejecuta ninguna decisión de inversión real.

## Por qué existe

Corporate Functions Data Office ya tiene un proceso de intake/aprobación/governance de
casos de uso de IA, con buen workflow management — pero sigue sin poder responder, solo
con esos datos: qué priorizar, qué escalar, qué es duplicado, qué no está entregando
valor, y dónde mover la inversión. Portfolio Intel es esa capa de inteligencia, construida
sobre el AI Use Case Inventory real de la empresa.

## Cómo se mapea a los 4 criterios de evaluación del challenge

| Criterio | Dónde vive |
|---|---|
| **Prioritization quality** | `tools/prioritization_tools.py` — composite score explicable (impacto, eficiencia de inversión, confianza, stage, escalabilidad), pesos documentados. Verificado: `tests/unit/test_prioritization_tools.py`, golden set. |
| **Reuse identification** | `tools/duplication_tools.py` — similitud textual real entre `business challenge`/`target state` + metadata compartida, sin embeddings. Encuentra los 4 clusters de duplicados del dataset, cero falsos positivos. |
| **Value realization** | `tools/value_realization_tools.py` — `on_track`/`at_risk`/`off_track` por 3 señales reales (sobre-costo, timeline vencida, barrera documentada). |
| **Recommendation explainability** | `tools/recommendation_tools.py` compone las tres anteriores con una tabla de reglas explícita (documentada con su rationale); `reporting/executive_report.py` renderiza todo en Markdown, cada línea trazable a una fila/columna real del dataset. |

Ver [`docs/architecture/adr/`](docs/architecture/adr/) para las decisiones de arquitectura
completas (ADRs 0001-0006), incluyendo en qué difiere deliberadamente de `finhive` (el
proyecto hermano de este mismo repo, ver más abajo) y por qué.

## Arquitectura

```
                    Top-Level Supervisor (routing, structured output)
                                     │
       ┌──────────────┬─────────────┼──────────────┬──────────────────┐
       ▼              ▼             ▼               ▼
 Prioritization  Reuse & Dup.  Value Realization  Portfolio
    Agent          Agent          Agent          Recommendation Agent
       │              │             │               │ (compone los 3 anteriores)
       └──────────────┴─────────────┴───────────────┘
              tools/ deterministas (nunca el LLM decide un número)
```

Un supervisor raíz rutea cada pregunta a uno de 4 agentes ReAct de dominio (un nivel menos
de jerarquía que `finhive`, ver ADR 0001); cada agente solo puede invocar sus propias
tools deterministas y narrar el resultado — nunca calcular un score, un match de
duplicado, o una recomendación por su cuenta (ver ADR 0002, la decisión de diseño central
de este proyecto). Guardrails de entrada (scope) y salida (groundedness) corren como
nodos del grafo, no como tools invocadas por el LLM.

## Stack

| Capa | Tecnología |
|---|---|
| Orquestación de agentes | LangGraph (`langgraph` + `langgraph-supervisor`) |
| LLM | Foundation Model APIs nativos de Databricks (Llama 3.3 70B / 3.1 8B) |
| Datos | Unity Catalog (Delta) en producción; CSVs locales en desarrollo — ver ADR 0003 |
| Evaluación | Golden set determinista (`data/eval/golden_set.json`), sin LLM-judge — ver ADR 0006 |
| Datos financieros/portfolio | AI Use Case Inventory de la empresa (sintético en este pase, ver abajo) |

## Estructura del repo

```
src/portfolio_intel/  paquete Python: agentes, tools, data, grafo, guardrails, reporting, evaluación
data/sample_docs/     dataset sintético del AI portfolio (regenerado, no commiteado — ver su README)
data/eval/             golden set de evaluación (data/eval/golden_set.json)
notebooks/00_demo.py   demo de 4 escenarios end-to-end, corre local o como notebook de Databricks Repos
tests/                 unit/ (núcleo determinista, sin LLM) + integration/ (estructural + live)
docs/architecture/adr/ decisiones de arquitectura de este proyecto (ADRs 0001-0006)
outputs/                artefactos generados al correr notebooks/00_demo.py (reporte ejecutivo, transcripts)
```

## Quickstart (desarrollo local)

Esta máquina de desarrollo no tiene conexión a Databricks (ver
`prompts/constraints_environment.md`) — el flujo de abajo corre todo lo que **no**
necesita un LLM real; el resto queda listo para correr en la compu de trabajo.

```bash
# el python del PATH puede ser demasiado nuevo para tener wheels de mlflow/matplotlib
# (ver CLAUDE.md) -- si falla, usar un intérprete Python 3.11 aparte.
pip install -e ".[dev]"

# generar el dataset sintético (no está commiteado, se regenera siempre igual)
python -m portfolio_intel.data.synthetic

# núcleo determinista: tests + golden set, sin LLM
pytest tests/unit tests/integration -v      # 38 passed, 3 deselected (los `live`)
python -m portfolio_intel.evaluation.run_eval   # 11/11 checks (100%)

# demo completa: reporte ejecutivo (determinista) + 4 escenarios de agentes
# (los agentes fallan limpio acá, sin Databricks -- ver la salida)
python notebooks/00_demo.py
```

## Para correr contra Databricks real (compu de trabajo)

```bash
cp .env.example .env
databricks auth login --host <tu-workspace-url>
```

Completar `.env`: `DATABRICKS_HOST`, `DATABRICKS_TOKEN`, `SQL_WAREHOUSE_ID` si se usa el
backend `databricks` (`PORTFOLIO_INTEL_DATA_BACKEND=databricks`). Con eso:

```bash
pytest tests/ -v -m live          # los 3 smoke tests contra el grafo real
python notebooks/00_demo.py       # los 4 escenarios ahora sí invocan el LLM real
```

Nota: las tablas Delta (`workspace.portfolio_intel.*`) todavía no están provisionadas en
ningún workspace real — `DatabricksDeltaStore` (`data/store.py`) está escrito y listo, pero
el DDL/carga inicial es trabajo pendiente (ver ADR 0003), fuera de alcance de este pase
según lo acordado con el usuario (`prompts/non_goals.md`).

## Dataset

No hay CSVs reales de la empresa todavía. `data/sample_docs/` tiene un dataset sintético
de 30 casos de uso de IA de una aseguradora ficticia, con el esquema exacto de columnas
que la empresa real usa (`RUAI Use Case` + `AI Use Case Detail`, ver
`src/portfolio_intel/data/schema.py`), construido a propósito (no relleno genérico, ver
ADR 0005) para que cada escenario — duplicados, casos en riesgo, candidatos a escalar o
discontinuar — sea real y verificable, no solo plausible. Ver
[`data/sample_docs/README.md`](data/sample_docs/README.md) para el detalle completo.

Reemplazar por los CSVs reales de la empresa es directo: mismo nombre de archivo, mismo
esquema de columnas — `data/store.py` no distingue entre datos sintéticos y reales.

## Sobre `finhive`

Este proyecto vive en el mismo repositorio que
[`finhive`](https://github.com/matiasadell/finhive) (branch `main`), un sistema
multiagente jerárquico de research financiero construido antes, sobre el mismo stack
(LangGraph + Databricks). Portfolio Intel reusa sus patrones arquitectónicos probados
(supervisor jerárquico, ReAct workers, guardrails como nodos de grafo, tools defensivas,
convención de ADRs) pero es un proyecto de dominio completamente distinto — ningún código
de negocio se comparte entre ambos, y `main`/`finhive` no se tocaron para construir esto
(todo el trabajo vive en la branch `hackathon-ai-portfolio-intelligence`).

## Autor

Facundo Mazzola — hackathon "AI Portfolio Intelligence Agent" (Corporate Functions Data
Office), sobre la base arquitectónica de `finhive` (Matías Adell).

## Licencia

MIT — ver [LICENSE](LICENSE).

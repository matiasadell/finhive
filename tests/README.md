# tests/

Dos suites, con un split deliberado por lo que cada una necesita para correr:

- **`unit/`** — el núcleo determinista del proyecto: `data/`, `tools/`,
  `reporting/`, `evaluation/`. Sin LLM, sin grafo, sin `langgraph`/`langchain`
  siquiera importados (ver la nota de import diferido en cada
  `tools/*.py`) -- corren con **cualquier** intérprete que tenga
  `pandas`/`numpy`/`pytest`, incluido el `python` del PATH de esta máquina
  (3.14, sin el resto de las deps del proyecto instaladas). 29 tests.

- **`integration/`** — todo lo que toca el grafo de LangGraph, dividido en dos:
  - `test_graph_structural.py`: **sin marcador**, corre siempre. Verifica el
    control de flujo real (`Command(goto=...)` de los guardrails y el router
    del supervisor) con un chat model fake (`tests/conftest.py`) -- sin red,
    sin LLM real. También confirma que `build_top_supervisor()` compila y
    que invocar el grafo de verdad falla en el punto correcto (la llamada al
    LLM, un error de auth/conexión) y no antes, por un bug de wiring.
  - `test_live_agents.py`: marcado `@pytest.mark.live`, **deselccionado por
    default** (`addopts = "-m 'not live'"` en `pyproject.toml`). Corre los
    agentes de verdad contra Databricks real -- solo anda en la compu de
    trabajo, con `.env` completo y `databricks auth login` hecho.

Estos dos necesitan el entorno con `langgraph`/`langchain`/
`databricks-langchain` instalados -- ver la nota de entorno en `CLAUDE.md`
(esta máquina de desarrollo usa un entorno conda aparte con Python 3.11 para
esto, no el `python` de 3.14 del PATH).

## Cómo correr

```bash
# núcleo determinista -- corre en cualquier intérprete con pandas/numpy
pytest tests/unit -v

# + control de flujo del grafo (sin red) -- necesita langgraph/langchain
pytest tests/unit tests/integration -v

# todo, incluidos los agentes reales -- solo en la compu de trabajo
pytest tests/unit tests/integration -v -m live
```

`uv run pytest tests/unit tests/integration -k "not live"` (o el comando
equivalente que use el entorno real) es el chequeo de referencia para "¿el
repo está sano en esta máquina de desarrollo?" -- ver `CLAUDE.md`.

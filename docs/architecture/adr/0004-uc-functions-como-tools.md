# ADR 0004 — Unity Catalog Functions como tools, sin Managed MCP servers

- **Estado**: aceptado
- **Fecha**: 2026-08-29

## Contexto

Al planificar las tools del dominio Macro, surgió la pregunta de cómo mapear el concepto
de MCP (Model Context Protocol — Era 5 de `main.pdf`) a la arquitectura de FinHive. Los
**Managed MCP servers** de Databricks (que exponen Vector Search, Genie y UC Functions vía
el protocolo MCP real, consumibles por cualquier cliente MCP) facturan cómputo serverless
general por invocación — no es gratis en el sentido de "incluido sin medir uso" como los
Foundation Model APIs nativos (ADR 0003).

## Decisión

Se usa **Unity Catalog Functions directamente como tools de LangChain**, sin pasar por el
protocolo MCP gestionado:

1. Cada función de datos (ej. `search_fred_series`, `get_fred_series_latest`) se escribe
   como función Python plana con type hints y docstring completo, y se **registra en
   Unity Catalog** (`workspace.finhive`) vía `DatabricksFunctionClient.create_python_function`
   — esto da la gobernanza/catálogo/schema-tipado que es el valor central de MCP, sin
   necesidad del protocolo en sí. Script genérico y reutilizable:
   `infra/databricks/register_uc_functions.py`.
2. Restricción encontrada al registrar: **Unity Catalog Functions no admite parámetros
   con valor default** (`limit: int = 5` falla con `UDF_UNSUPPORTED_PARAMETER_DEFAULT_VALUE`)
   — todos los parámetros de las tools quedan obligatorios, documentado el valor
   recomendado en el docstring en su lugar.
3. Para la **ejecución** de la tool en el grafo de LangGraph, se evita
   `UCFunctionToolkit` con `execution_mode="local"`: se probó y falla en Windows,
   porque el runner que genera (`unitycatalog/ai/core/executor/local_subprocess.py`)
   hace `import resource` — módulo de la stdlib **Unix-only**, inexistente en Windows.
   El subproceso crashea antes de imprimir nada a stdout, y la librería lo reporta como
   `"The function execution has been terminated with a signal"`. Consecuencia observada
   en la práctica: el worker recibía ese error genérico como resultado de la tool y el
   LLM, en vez de admitir el fallo, **alucinó cifras plausibles** (ej. "Fed Funds Rate
   5.25%" cuando el valor real era 3.63%) — un recordatorio concreto de por qué CRAG/
   grounding importa: un fallo silencioso de tool es indistinguible de un dato real si
   nadie lo valida.
4. En su lugar, las mismas funciones Python se envuelven directamente como
   `langchain_core.tools.tool` y se ejecutan en el propio proceso — sin subprocess, sin
   sandboxing, sin latencia de red ni cuota de cómputo serverless. UC sigue siendo la
   fuente de verdad del contrato/schema (visible y gobernado en el catálogo), solo cambia
   el mecanismo de invocación en tiempo de ejecución.

## Consecuencias

- Cero costo adicional de cómputo serverless para tool calls (ni el de un Managed MCP
  server, ni el de `UCFunctionToolkit` en modo `serverless`).
- Cero dependencia de un bug de compatibilidad Windows-específico en una librería de
  terceros en evolución rápida (`unitycatalog-ai`).
- Se pierde la ejecución "oficialmente gobernada" via UC en runtime — mitigado: si más
  adelante se despliega este sistema desde un notebook de Databricks (Linux, donde
  `import resource` sí existe), se puede volver a `UCFunctionToolkit(execution_mode="local")`
  o pasar a `"serverless"` sin cambiar el resto del grafo, ya que las funciones ya están
  registradas.
- Cada dominio nuevo (equity, portfolio_risk, news_sentiment, crypto_alt) repite este
  mismo patrón: función plana en `src/finhive/tools/<dominio>_data.py`, registro vía
  `infra/databricks/register_uc_functions.py`, wrap con `langchain_core.tools.tool` en
  `src/finhive/agents/<dominio>/workers.py`.

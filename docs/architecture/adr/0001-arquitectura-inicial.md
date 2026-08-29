# ADR 0001 — Arquitectura inicial de FinHive

- **Estado**: aceptado
- **Fecha**: 2026-08-29

## Contexto

FinHive es un sistema multiagente jerárquico de análisis financiero, pensado como
proyecto insignia para portfolio/CV: aplicar la mayor cantidad posible de conceptos de
arquitecturas agénticas (documentados en `docs/theory/main.pdf` y `docs/theory/Summary.pdf`)
sobre un caso de uso financiero real, desplegado sobre Databricks Free Edition.

La base de código parte del patrón "Hierarchical Agent Teams" mostrado en el notebook de
referencia del bootcamp (`.reference/8-multiagent.ipynb`, no versionado en este repo):
supervisores compuestos por subgrafos, con `Command` para enrutar entre nodos y
`langgraph_supervisor` para los supervisores simples.

## Decisiones

| # | Pregunta | Decisión | Razón |
|---|---|---|---|
| 1 | Alcance de dominios | 5 sub-supervisores (Completo) | Balance entre cobertura demostrable y tiempo de desarrollo |
| 2 | Backend LLM | Claude (Anthropic) como *External Model* en Databricks Model Serving, vía AI Gateway | El usuario ya usa Claude Code; permite mostrar gobernanza de gateway sobre un modelo externo |
| 3 | Datos del RAG | Fuentes gratis + free-tier (yfinance, SEC EDGAR, FRED, Alpha Vantage) | Cero costo recurrente para un proyecto de portfolio |
| 4 | Entregable final | Repo + demo desplegada + artículo técnico | Máximo impacto para reclutadores sin llegar al video |
| 5 | Vector store | Databricks Vector Search, endpoint único, índice consolidado con columna `domain` | Free Edition limita a 1 endpoint / 1 search unit; un índice con metadata filtrable es más robusto que fragmentar en varios índices pequeños |
| 6 | Observabilidad | MLflow Tracing/Evaluate **+** LangSmith | El usuario quiso ambos explícitamente, para comparar los dos enfoques |
| 7 | Flujo de desarrollo | Databricks Repos + notebooks nativos sincronizados a GitHub | Preferencia explícita del usuario sobre Asset Bundles |
| 8 | Guardrails | Completos (tópico, seguridad, groundedness, jailbreak) + disclaimers financieros | Dominio financiero → riesgo legal/reputacional si el sistema sugiere asesoramiento real |
| 9 | Acceso a Databricks | CLI autenticada localmente por el usuario (`databricks auth login`, OAuth); comandos ejecutados con esa sesión | Ningún token pasa por el chat en ningún momento |
| 10 | UI de demo | Streamlit sobre Databricks Apps | Rápido de armar, buen soporte nativo, familiar para reclutadores técnicos |
| 11 | Dominios finales | Macro & Política Monetaria · Equity Research & Fundamentals · Portfolio & Risk Management · News & Sentiment · Crypto & Alternativos | Confirmado tal cual por el usuario |
| 12 | Nombre del proyecto | FinHive (paquete `finhive`) | Metáfora de colmena: supervisor raíz = reina, sub-supervisores = obreras especializadas |

## Hallazgo de seguridad

`8-multiagent.ipynb` (material del bootcamp, no autoría original de este proyecto) tenía
una API key de Tavily hardcodeada en texto plano. Se excluyó del repo público
(`.reference/`, gitignoreado) y se le pidió al usuario rotarla en el dashboard de Tavily,
independientemente de si el notebook se publica o no.

## Mapa de conceptos teóricos aplicados

Cada concepto del timeline (`main.pdf`) y del bootcamp (`Summary.pdf`) tiene un lugar
concreto en la arquitectura — no son referencias decorativas, son decisiones de diseño:

| Concepto (paper/sección) | Dónde se aplica en FinHive |
|---|---|
| ReAct (Yao et al., 2022) | Todo worker leaf usa `create_react_agent` |
| Reflexion (Shinn et al., 2023) | Capa de guardrails de groundedness: crítica verbal del propio output antes de responder |
| Generative Agents / MemGPT | Memoria de dos niveles: checkpointer de LangGraph (conversación) + memoria persistente de perfil/portfolio en Lakebase |
| Self-RAG / Corrective RAG (CRAG) | Grading de relevancia del retrieval antes de generar; fallback a Tavily si es irrelevante |
| RAPTOR | Árbol de resúmenes recursivo para 10-K/10-Q largos del sub-supervisor de Equity |
| Adaptive-RAG | Router de complejidad en el top-level supervisor: trivial / single-domain / multi-domain |
| Modular RAG | Pipeline de retrieval en `src/finhive/rag/` como módulos intercambiables (retrieval, rerank, query enhancement) |
| HyDE + Query Expansion + Decomposition | Capa de query enhancement antes de cada búsqueda en Vector Search |
| Multi-Agent Network / Supervisor / Hierarchical | Los 3 patrones del notebook de referencia, aplicados literalmente: leaf workers en red dentro de un dominio, sub-supervisores tipo Supervisor, y el top-level como Hierarchical Teams |
| Mixture-of-Agents | Síntesis final del top supervisor cuando combina resultados de 2+ dominios |
| MCP | Unity Catalog Functions expuestas como tools con interfaz estilo MCP |
| LLM Gateway (Summary.pdf §19) | Databricks AI Gateway gobernando el External Model de Anthropic |
| Guardrails (Summary.pdf §18) | `src/finhive/guardrails/`: tópico, seguridad, groundedness, jailbreak |
| LLM-as-judge / evaluación (Summary.pdf §20) | MLflow Evaluate + LangSmith |

## Consecuencias

- El índice único de Vector Search obliga a diseñar bien el esquema de metadata
  (`domain`, `source`, `date`) desde el principio — cambiarlo después implica reindexar.
- Depender de un `External Model` (Anthropic) vía AI Gateway en vez de un modelo nativo
  de Databricks introduce una dependencia de red/costo externo, pero es la decisión
  explícita del usuario y demuestra mejor el concepto de gateway multi-proveedor.
- Guardrails completos + disclaimers agregan latencia y complejidad, aceptado a cambio
  de reducir el riesgo de que el sistema parezca dar asesoramiento financiero real.

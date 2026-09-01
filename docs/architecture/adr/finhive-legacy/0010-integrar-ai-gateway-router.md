# ADR 0010 — Integrar el model routing de Unity AI Gateway a `src/finhive`

- **Estado**: aceptado
- **Fecha**: 2026-08-29
- **Supersede**: la conclusión de "no integrado todavía" de ADR 0009

## Contexto

ADR 0009 dejó `finhive_router` y la idea de un router de embeddings como capacidad
verificada pero standalone — `ChatDatabricks` no sabía hablarle al path nuevo de AI
Gateway. El usuario pidió explícitamente conectar esto de verdad, y compartió el ejemplo
de conexión que da la propia UI de Databricks: cliente `openai.OpenAI` estándar, con
`base_url="https://<workspace>/ai-gateway/mlflow/v1"` y `api_key=DATABRICKS_TOKEN`.

Eso destrabó el problema: `langchain_openai.ChatOpenAI` (el wrapper de LangChain sobre el
cliente `openai` estándar) sí puede apuntar a esa `base_url` — no hacía falta esperar a
que `databricks-langchain` soporte el path nuevo, alcanzaba con usar el cliente
OpenAI-compatible que Databricks ya expone.

## Decisión

Se agregaron a `finhive.config.settings`:

- `get_databricks_host()` / `get_databricks_token()` — leen `DATABRICKS_HOST` /
  `DATABRICKS_TOKEN` de env. A diferencia del resto del proyecto (OAuth vía
  `DATABRICKS_CONFIG_PROFILE`, sin token estático), el cliente OpenAI-compatible necesita
  un Bearer token fijo — un Personal Access Token generado con `databricks tokens create`.
- `get_router_chat_model()` — `ChatOpenAI` apuntando a `AI_GATEWAY_ROUTER_MODEL`
  (`workspace.finhive.finhive_router`) vía `/ai-gateway/mlflow/v1`.
- `get_gateway_embeddings()` — `OpenAIEmbeddings` apuntando a `AI_GATEWAY_EMBEDDINGS_MODEL`
  (`workspace.finhive.finhive_embeddings`, model service nuevo creado para esto, 100% a
  `gte_large_en_v1_5` — sin sentido "rutear" entre modelos de embeddings distintos, porque
  producen espacios vectoriales no comparables entre sí; el valor acá es la gobernanza de
  UC/AI Gateway, no el routing).

`src/finhive/graph/top_supervisor.py` — el nodo más crítico del grafo (decide a qué
equipo delegar cada turno) — ahora usa `get_router_chat_model()` en vez de
`get_chat_model("supervisor")`. Verificado end-to-end: la jerarquía completa sigue
funcionando, con la ventaja añadida de que la decisión de routing la puede servir
cualquiera de los dos modelos del gateway.

## Dos problemas encontrados y resueltos en el camino

1. **Embeddings fallaban con 400 BAD_REQUEST** ("Parameter 'input' must be a string or a
   list of strings"). Causa: `OpenAIEmbeddings` pre-tokeniza con `tiktoken` por default,
   asumiendo un modelo real de OpenAI, y manda arrays de token IDs. Desactivar
   `tiktoken_enabled` no alcanza — cae a un fallback con `transformers` (no instalado, y
   que igual tokenizaría). Fix real: `check_embedding_ctx_length=False`, que salta ese
   codepath entero y manda el texto plano tal cual.

2. **Warning de Pydantic sobre `content` con un bloque `"type": "reasoning"`** al invocar
   el router: cuando el tráfico cae en GPT OSS 120B (modelo de razonamiento) en vez de
   Llama 3.3 70B, el formato de la respuesta incluye un bloque de reasoning que Llama no
   produce. No rompió nada (la respuesta se sigue procesando bien), pero es una
   inconsistencia real entre destinos de un mismo router a tener en cuenta si en el futuro
   se agregan modelos con formatos de salida más distintos entre sí.

## Consecuencias

- El sistema tiene ahora dos formas de instanciar un LLM: `get_chat_model(tier)`
  (`ChatDatabricks`, endpoint único, usado por dominios y workers) y
  `get_router_chat_model()` (`ChatOpenAI` vía AI Gateway, routing real, usado por el
  top-level supervisor). Es una asimetría deliberada, no un descuido — el punto de mayor
  criticidad del sistema es el único que se benefició de la resiliencia extra por ahora.
- `DATABRICKS_TOKEN` es el primer secret estático de larga vida que tiene el proyecto —
  todo lo demás usa OAuth de corta vida. Generado con `databricks tokens create
  --lifetime-seconds 7776000` (~90 días); rotar antes de que expire.
- El notebook (`00_demo.py`) no necesita ese PAT: usa el token de la propia ejecución del
  notebook (`dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken()`),
  más simple y de vida más corta que guardar un secret estático — solo hace falta el PAT
  para desarrollo local.
- Extender esto a los sub-supervisores de dominio (no solo el top-level) es directo si se
  decide más adelante: mismo patrón, otro model service con otra combinación de destinos.

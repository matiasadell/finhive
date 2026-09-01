# ADR 0017 — RAG real sobre 10-K de SEC EDGAR (Vector Search)

- **Estado**: aceptado
- **Fecha**: 2026-08-31

## Contexto

La auditoría completa del proyecto (post ADR 0016) encontró que "Vector Search"
aparecía en el README/Stack como si fuera parte activa de la arquitectura, pero
la infra (`finhive_vs_endpoint`, `STANDARD`/`ONLINE`) estaba provisionada y
vacía — `src/finhive/rag/__init__.py` era un docstring de una línea, sin
ingesta ni índice. El equipo de equity solo podía traer datos **estructurados**
de un filing (`get_sec_company_facts`, XBRL) o metadata (`search_sec_filings`,
fecha + accession number) — no podía responder nada sobre el contenido
narrativo real ("¿qué riesgos de cadena de suministro menciona el 10-K de
Apple?"). Consultado el usuario sobre qué hacer con ese hueco (usarlo de
verdad o desestimarlo), la decisión fue cerrarlo con una prueba de concepto
real, no descartarlo.

## Decisión de diseño

**Alcance chico a propósito**: el último 10-K de **AAPL y MSFT** (los mismos
tickers que ya aparecen en el golden set y en las preguntas de demo) — no una
ingesta general de todas las empresas. Es una prueba de concepto real de RAG
narrativo, no un pipeline de producción.

**Índice Delta Sync, no Direct Access** (`databricks.ai_search.client.VectorSearchClient`
— el paquete `databricks-vectorsearch` está deprecado y renombrado a
`databricks-ai-search`; `databricks.vector_search.*` sigue funcionando como
re-export delgado, pero el código nuevo usa el import `databricks.ai_search.*`
directo): Databricks calcula los embeddings solo contra `databricks-gte-large-en`
(la misma constante `EMBEDDING_ENDPOINT` que ya existía en `settings.py`, sin
uso hasta ahora), sin que el código tenga que embeber a mano.
`pipeline_type="TRIGGERED"`: sincroniza solo cuando se llama a `.sync()`, no
cómputo continuo — mismo criterio de costo que `scale_to_zero` en ADR 0015.

**Chunking simple, no parsing de secciones**: el HTML de un 10-K varía mucho
de formato entre empresas — parsear "Item 1A" de forma estructural es frágil.
`finhive/rag/ingest.py` reusa la resolución de CIK ya escrita en
`equity_data.py` (renombrada de `_ticker_to_cik`/`_sec_headers`/
`_SEC_SUBMISSIONS_URL` a pública, sin `_`, porque ahora se comparte entre dos
módulos), suma el campo `primaryDocument` de `submissions/CIK{cik}.json`
(ya venía en esa respuesta; `search_sec_filings` simplemente no lo usaba) para
armar la URL real del documento, y trocea el texto plano en chunks de ~1500
caracteres con 200 de solapamiento. La búsqueda semántica encuentra los chunks
relevantes igual, sin depender de que el parsing de secciones haya sido exacto.

## Los bugs reales encontrados en el proceso

### 1. El documento primario es inline XBRL: ~14KB de metadata mezclada con el texto

Probando `fetch_filing_text("AAPL", "10-K")` en local antes de tocar infra de
Databricks (sin costo, solo HTTP a SEC EDGAR): los primeros chunks resultantes
eran pura basura — namespaces XBRL, fechas y nombres de "member" en vez de
texto del reporte (ej. `http://fasb.org/us-gaap/2025#LongTermDebtNoncurrent`).
Causa raíz: el `primaryDocument` de un 10-K moderno es un archivo **inline
XBRL (iXBRL)** — el HTML visible del reporte con un bloque `<ix:header>`
incrustado (definiciones de contexto/unit XBRL, ~13KB solo en el 10-K de
Apple) y un bloque `<ix:hidden>` (hechos etiquetados nunca mostrados). Sin
removerlos, `BeautifulSoup.get_text()` mezcla esa metadata con el inicio del
documento real. Fix en `ingest.py`: `soup(["script", "style", "ix:header",
"ix:hidden"]).decompose()` más un pase adicional por elementos con
`style="display:none"`. Verificado en vivo para AAPL y MSFT: el primer chunk
después del fix arranca directo en "UNITED STATES SECURITIES AND EXCHANGE
COMMISSION..." — la portada real del 10-K, no metadata.

### 2. `VectorSearchClient` no acepta el mismo OAuth ambiente que el resto del proyecto

Todo el resto del código (`WorkspaceClient()` en `finhive.memory.store`,
`DatabricksFunctionClient()` en `register_uc_functions.py`) funciona sin
argumentos, autenticándose vía el perfil OAuth de `databricks auth login`
(`auth_type: databricks-cli`). `VectorSearchClient()` sin argumentos, en
cambio, tira `InvalidInputException: Please specify either personal access
token or service principal client ID and secret` — ese cliente solo soporta
PAT explícito, service principal OAuth M2M, o auto-detección dentro de un
notebook/Model Serving; no el perfil OAuth de la CLI. Fix: pasarle
`workspace_url=get_databricks_host()` y
`personal_access_token=get_databricks_token()` explícitos — el mismo PAT de
larga duración (`DATABRICKS_TOKEN`/`.env`, o el secret `databricks_token`
dentro del Agent desplegado) que ya usa `get_router_chat_model()` para el
cliente OpenAI-compatible del AI Gateway (ADR 0009/0015). Sin este fix,
`setup_vector_search.py` fallaba después de insertar los chunks pero antes de
crear el índice, y `search_filing_content` habría fallado igual dentro del
Agent desplegado.

## Archivos nuevos/modificados

- `src/finhive/rag/ingest.py` (nuevo) — `fetch_filing_text(ticker, form_type)`
  y `chunk_text(text, chunk_size=1500, overlap=200)`.
- `infra/databricks/setup_vector_search.py` (nuevo, patrón standalone
  idempotente) — crea `workspace.finhive.equity_filing_chunks` (con
  `delta.enableChangeDataFeed = true`), ingesta AAPL + MSFT si no están ya
  cargados, crea/sincroniza el índice `equity_filing_chunks_index`.
- `src/finhive/config/settings.py` — `VECTOR_SEARCH_ENDPOINT`,
  `EQUITY_FILINGS_INDEX`.
- `src/finhive/tools/equity_data.py` — `search_filing_content(ticker, query)`,
  nueva tool; `_ticker_to_cik`/`_sec_headers`/`_SEC_SUBMISSIONS_URL` pasan a
  ser públicos (sin `_`) por el reuso desde `finhive.rag.ingest`.
- `src/finhive/agents/equity/workers.py` — `search_filing_content` agregada
  solo a `filings_worker` (no a `fundamentals_worker`/`technical_worker`),
  prompt actualizado aclarando la cobertura limitada a AAPL/MSFT.
- `infra/databricks/register_uc_functions.py` — `search_filing_content`
  agregada a la lista de funciones de Equity.

## Verificación

1. `fetch_filing_text`/`chunk_text` probados en local para AAPL y MSFT (sin
   costo de Databricks): 161 y 288 chunks respectivamente, texto real desde
   el primer chunk después del fix del bug #1.
2. `setup_vector_search.py` corrido contra Databricks real: tabla creada,
   161 (AAPL) + 288 (MSFT) chunks insertados, índice Delta Sync creado y
   sincronizado sobre `finhive_vs_endpoint`.
3. `search_filing_content("AAPL", "riesgos de cadena de suministro")` probado
   directo, antes de conectarlo al agente: devolvió 3 extractos reales y
   relevantes del 10-K (fallas de IT en la cadena de suministro, desastres
   naturales, accidentes industriales en proveedores) — no ruido XBRL, no
   contenido genérico.
4. Equipo de Equity completo (`build_equity_supervisor()`), pregunta
   "¿Qué riesgos de cadena de suministro menciona el 10-K de Apple?": el
   supervisor de dominio enrutó a `filings_worker`, que llamó
   `search_filing_content(ticker="AAPL", query="riesgos de cadena de
   suministro")` y respondió con una lista de riesgos grounded en el texto
   real del filing (fallas de IT, desastres naturales, accidentes
   industriales en proveedores, problemas de calidad, write-downs de
   inventario) — no alucinado, no conocimiento genérico del LLM.
5. `uv run ruff check` sobre todos los archivos nuevos/modificados: sin
   errores.

## Consecuencias

- El README/Stack ya no sobrevende Vector Search como cobertura general —
  se documenta explícitamente como prueba de concepto de 2 tickers.
- `search_filing_content` es la primera tool del proyecto que depende de
  infraestructura propia con estado (el índice), no solo de una API externa
  de terceros — si el índice se borra o el endpoint se recrea, hay que
  volver a correr `setup_vector_search.py` antes de que la tool funcione.
- Extender la cobertura a más tickers o filings (10-Q, proxies) es directo:
  agregar el ticker a `_TICKERS` en `setup_vector_search.py` y correrlo de
  nuevo — es idempotente, no reingesta lo que ya está.

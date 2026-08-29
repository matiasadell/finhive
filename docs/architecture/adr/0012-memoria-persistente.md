# ADR 0012 — Memoria persistente: sesión + hechos de largo plazo (MemGPT), sobre Delta/UC

- **Estado**: aceptado
- **Fecha**: 2026-08-29

## Contexto

El plan original (README, fase de diseño inicial) nombraba "Lakebase (Postgres
serverless)" como backend de memoria persistente. Antes de construir sobre eso, se
verificó si tiene sentido para este proyecto — mismo criterio que ya descartó Groq (ADR
0002) y la creación de un catalog nuevo (ADR 0001): no asumir que algo es gratis en Free
Edition sin comprobarlo.

`databricks database create-database-instance` existe y es alcanzable desde la cuenta,
pero es **Public Preview** y no hay forma de confirmar de antemano si Free Edition lo
habilita gratis sin efectivamente crear una instancia — una acción de infraestructura
real, potencialmente lenta de revertir limpiamente. Se le preguntó al usuario en vez de
asumir cualquiera de los dos lados. Decisión: usar en cambio una **tabla Delta en
`workspace.finhive`**, escrita/leída vía el SQL warehouse serverless
(`Serverless Starter Warehouse`, `1a9a12e190f307b2`) que ya está provisionado y
verificado en $0 desde el arranque del proyecto — mismo patrón que ADR 0004 (UC
Functions en vez de Managed MCP servers): preferir un recurso ya pago/gratis existente
por sobre uno nuevo de estado incierto.

## Decisión

### Backend: Statement Execution API, no `langgraph.checkpoint.*`

`finhive.memory.store.execute_sql()` corre SQL parametrizado contra el warehouse vía
`databricks.sdk.WorkspaceClient().statement_execution` — mismo patrón de auth ambiente
(`DATABRICKS_CONFIG_PROFILE`, OAuth) que ya usa `register_uc_functions.py`, sin
dependencia nueva.

Deliberadamente **no** se implementó un `BaseCheckpointSaver` de LangGraph (el protocolo
nativo para persistencia de estado). Ese protocolo versiona el grafo completo en cada
transición de nodo — pensado para time-travel / resumir una ejecución interrumpida desde
cualquier punto. Contra la Statement Execution API (con latencia real de red por
sentencia, no una conexión persistente de baja latencia como tendría Postgres), eso
significaría un round-trip HTTP por cada paso del grafo — demasiado costo para un
sistema donde cada `graph.invoke()` corre de punta a punta en una sola pasada, sin
necesidad real de resumir desde la mitad. En cambio, `finhive.memory.session` guarda y
carga la lista completa de mensajes de un thread una única vez al principio y al final
de cada invocación — más simple, y 3 round-trips totales por invocación (1 SELECT + 1
DELETE + 1 INSERT multi-fila) en vez de uno por nodo del grafo.

### Dos tablas, dos niveles de memoria (patrón MemGPT — Packer et al., 2023)

- **`workspace.finhive.conversation_sessions`** — memoria de sesión: continuidad dentro
  de un mismo `thread_id` entre invocaciones separadas del proceso. Cada fila es un
  mensaje (`thread_id, turn_index, role, msg_name, content, created_at`).
- **`workspace.finhive.conversation_facts`** — memoria archival: hechos durables que
  valen la pena recordar entre conversaciones DISTINTAS (ej. un ticker o sector que el
  usuario consulta seguido). El modelo worker decide, con `with_structured_output`
  (mismo patrón que los guardrails, ADR 0011), si una conversación terminada dejó algún
  hecho de ese tipo.

`recall_relevant_facts()` trae simplemente los N hechos más recientes (sin búsqueda
semántica) — no hay índice de Vector Search creado todavía para FinHive. Es una
simplificación honesta, no un intento fallido: para el volumen de hechos que acumula una
demo, alcanza. Recall por similitud semántica es la extensión natural el día que haya
embeddings de por medio (mismo work item que "RAG estilo RAPTOR", ya en trabajo futuro).

### Nodos propios del grafo, no tools invocadas por el LLM

`memory_recall_node` y `memory_remember_node` (`finhive/memory/nodes.py`) son pasos
deterministas del pipeline — mismo criterio que ADR 0011 para los guardrails, por la
misma razón: darle al supervisor raíz la capacidad de invocar tools de memoria en medio
del routing lo convertiría en un agente de tool-calling además de router, con dos modos
de decisión mezclados en el mismo nodo. Alcance limitado a nivel top-level únicamente
(no replicado por sub-supervisor), consistente con la misma decisión ya tomada para
guardrails.

Flujo final del grafo: `START -> input_guardrail -> memory_recall -> supervisor ->
(equipos) -> supervisor -> ... -> output_guardrail -> memory_remember -> END`. Un pedido
rechazado por `input_guardrail` nunca toca memoria (ni recall ni remember) — no hay
sesión que continuar ni hecho que extraer de un pedido fuera de scope.

El `thread_id` que separa una conversación de otra viaja por el `RunnableConfig`
estándar de LangGraph (`config={"configurable": {"thread_id": ...}}`), no por
`FinHiveState` — ninguna invocación existente que no lo pase se rompe, cae a un thread
`"default"` compartido.

## Bug real encontrado: import circular entre `finhive.memory` y `finhive.graph`

`finhive/memory/nodes.py` necesita `FinHiveState` de `finhive.graph.state`, y
`finhive/graph/top_supervisor.py` necesita los nodos de `finhive.memory`. Mientras
`finhive/memory/__init__.py` reexportara esos nodos de forma eager (`from
finhive.memory.nodes import ...`), cualquier código que importe `finhive.memory` (o un
submódulo suyo, como `finhive.memory.store`) **antes** de que `finhive.graph` haya sido
tocado por primera vez disparaba un ciclo real: Python debe terminar de ejecutar
`finhive/memory/__init__.py` antes de permitir importar `finhive.memory.store`, pero
`finhive/memory/__init__.py` (vía `nodes.py`) dispara la ejecución completa de
`finhive/graph/__init__.py`, que a su vez necesita atributos de `finhive.memory` que
todavía no existen (el módulo está a mitad de inicializarse) → `ImportError`.

Se manifestó al correr `infra/databricks/setup_memory_tables.py` (que solo necesita
`execute_sql` de `store.py`, sin tocar `finhive.graph` para nada) — un caso de uso real,
no un artefacto de test. `tests/integration/` nunca lo disparó porque ahí siempre se
entra por `from finhive.graph import build_top_supervisor` primero.

**Fix**: `finhive/memory/__init__.py` no reexporta nada de `nodes.py` — solo el
docstring del paquete. `top_supervisor.py` importa los 4 nodos (guardrails y memoria)
directo de sus submódulos (`finhive.guardrails.input_guardrail`,
`finhive.guardrails.output_guardrail`, `finhive.memory.nodes`), no de los `__init__.py`
de los paquetes. Regla general que queda de acá: un paquete que depende de otro que a su
vez lo importa de vuelta no debe reexportar eager en su `__init__.py` — solo el
submódulo que efectivamente lo necesita, importado directo.

## Consecuencias

- **Costo/latencia**: cada conversación completa paga 3 round-trips SQL extra (recall:
  1 SELECT de sesión + 1 SELECT de hechos; remember: 1 DELETE + 1 INSERT multi-fila) más
  2 llamadas al modelo worker (clasificar hecho durable). El warehouse serverless tiene
  cold-start (~10-20s) si estuvo inactivo más de `auto_stop_mins` (10 min) — primera
  invocación de una sesión de trabajo será más lenta que las siguientes.
- **Sin truncado de historial**: `conversation_sessions` guarda la lista completa de
  mensajes de un thread sin límite ni resumen — crece linealmente con cada turno.
  Aceptable para una demo, primera limitación real a resolver si esto se usara con
  conversaciones largas de verdad.
- **`recall_relevant_facts` sin búsqueda semántica**: trae los N hechos más recientes
  globalmente, no los más relevantes a la pregunta actual — simplificación documentada,
  no bug.
- Verificado en vivo (`tests/integration/test_memory.py`): dos `graph.invoke()`
  separados con el mismo `thread_id` — el segundo, sin el historial recuperado, no tiene
  forma de interpretar una pregunta de seguimiento ("¿y hace cuánto que lo consultamos
  por primera vez?"); con `memory_recall_node` funcionando, sí. Threads distintos no
  comparten sesión (verificado por separado).
- Nuevo script de infraestructura: `infra/databricks/setup_memory_tables.py`
  (idempotente, `CREATE TABLE IF NOT EXISTS`) — correrlo una vez antes de usar memoria
  persistente, igual que `register_uc_functions.py` para las tools.

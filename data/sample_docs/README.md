# Sample docs — dataset sintético del AI portfolio

No hay CSVs reales todavía (ver `prompts/constraints_data.md`) — estos dos archivos
son generados por `src/portfolio_intel/data/synthetic.py` (`python -m
portfolio_intel.data.synthetic` desde la raíz del repo, con `src/` en el
`PYTHONPATH`), no editados a mano. **No están commiteados a git** — mismo
`.gitignore` que ya usaba finhive para `data/` ("los corpora viven en Unity
Catalog Volumes, no en git"). Como el generador es determinístico (sin
`random` sin seed fija), correrlo produce siempre exactamente los mismos 30
casos de uso, así que no hace falta commitear el output para que sea
reproducible — alcanza con tener `synthetic.py` (que sí está commiteado). Si
alguien clona el repo, el primer paso es correr el generador. Si el usuario provee los CSVs reales más
adelante, van acá mismo con **el mismo nombre de archivo y el mismo esquema de
columnas** (`src/portfolio_intel/data/schema.py`), y todo lo demás sigue
funcionando sin cambios — `data/store.py` no sabe si el archivo es sintético o
real.

- `rua_use_case_inventory.csv` — 30 filas, esquema "RUAI Use Case" (inventario +
  tracking de aprobación).
- `ai_use_case_detail.csv` — 30 filas, esquema "AI Use Case Detail" (value/KPI,
  inversión, impacto, contexto de negocio). Join key: `title` (RUAI) ==
  `use case` (Detail), idénticos por construcción.

30 casos de uso de una aseguradora ficticia, repartidos en 8 LOBs (Claims,
Underwriting, Fraud & SIU, Actuarial, Marketing, Customer Service, IT Operations,
HR). El dataset está **deliberadamente construido**, no relleno genérico — cada
escenario de la demo (`notebooks/00_demo.py`) y cada entrada del golden set
(`data/eval/golden_set.json`) referencia ids concretos de acá:

## Top tier — candidatos a "Scale" (alto impacto/confianza/escalabilidad)

`UC-001` a `UC-006` — todos `confidence_level=High`, `scalability=High`, en
`Full Production`/`Limited Production`.

## Pares casi-duplicados (la historia de reuse/consolidación)

Mismo dominio de negocio, texto de `business challenge`/`target state` con
overlap fuerte a propósito, construidos por equipos/LOBs distintos sin saberlo:

- **Cluster A** — chatbot de status de claims: `UC-007` (región Este) vs.
  `UC-008` (región Oeste).
- **Cluster B** — detección de patrones de fraude: `UC-009` (SIU) vs. `UC-010`
  (Underwriting).
- **Cluster C** — screening de candidatos: `UC-011` (HR) vs. `UC-012` (IT
  Recruiting).
- **Cluster D** — personalización de ofertas de renovación: `UC-013` (canal
  digital) vs. `UC-014` (call center).

## At risk / off track — no van a realizar el valor prometido

`UC-011`, `UC-015`, `UC-016`, `UC-017`, `UC-018`, `UC-019` — cada uno con una
razón concreta y distinta en `insight learned or barriers` (sobre-costo,
accuracy insuficiente, datos incompletos, bloqueo regulatorio, sin owner
técnico). `UC-015` además tiene `value return begins in` ya vencida relativa a
"hoy" (2026-09-01) sin haber llegado a `Full Production`.

## Candidatos a "Discontinue"

`UC-010`, `UC-012`, `UC-020`, `UC-021`, `UC-022`, `UC-023`, `UC-024` — baja
confianza/impacto/escalabilidad, estancados en `Ideation`/`On Hold` sin
progreso. `UC-010` y `UC-012` son además miembros de un cluster duplicado
(clusters B y C), así que su recomendación esperada es *Consolidate* con su
par, no un `Discontinue` aislado — ver la regla de precedencia en
`tools/recommendation_tools.py`.

## Relleno "Monitor"

`UC-025` a `UC-030` — perfil intermedio en todas las dimensiones, sin
escenario especial asociado; están para que el portfolio no sea solo casos
extremos.

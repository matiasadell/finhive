# ADR 0006 — Descripciones de equipo en el router para desambiguar preguntas de frontera

- **Estado**: aceptado
- **Fecha**: 2026-08-29

## Contexto

Con 4 equipos reales (`macro`, `equity`, `portfolio_risk`, `news_sentiment`), apareció un
caso de ruteo incorrecto real: la pregunta "¿cuándo es el próximo earnings de Apple?" se
enrutó a `equity`, no a `news_sentiment`.

"Earnings" es ambiguo entre los dos dominios: `equity` cubre resultados **ya reportados**
(vía `get_sec_company_facts` sobre datos históricos de SEC EDGAR); `news_sentiment` cubre
el **calendario de próximos** earnings (vía `get_earnings_calendar` de Alpha Vantage). El
router del top-level supervisor solo recibía los *nombres* de los equipos
(`{members}`, ej. `['macro', 'equity', 'portfolio_risk', 'news_sentiment']`), sin ninguna
descripción de qué cubre cada uno — nada le daba al LLM la información necesaria para
distinguir "resultado ya reportado" de "fecha de un resultado futuro".

Consecuencia observada: `equity` recibió la pregunta, su `filings_worker` intentó
`get_sec_company_facts(concept="EarningsReleaseDate")` — un tag XBRL que no existe (404) —
y en vez de reportar que no tenía esa información, el equipo **alucinó una fecha
incorrecta** (dijo "octubre de 2025"; la fecha real, confirmada por
`get_earnings_calendar`, es 2026-10-29). Mismo patrón de fondo que ADR 0004 (Windows/UC
Functions): un fallo o gap de cobertura silencioso se resuelve con una respuesta plausible
en vez de una admisión de "no lo sé" — un caso concreto de por qué el grounding importa,
y evidencia de que el guardrail de tópico/groundedness (todavía pendiente en el roadmap)
tiene trabajo real que hacer acá, no es una casilla decorativa.

## Decisión

Se agregó `_TEAM_DESCRIPTIONS` en `top_supervisor.py`: una descripción corta por equipo,
incluyendo líneas explícitas de "esto NO es de este equipo" en los casos de frontera ya
conocidos (ej. la descripción de `equity` dice literalmente "NO calendario de próximos
earnings — eso es news_sentiment"). El prompt del router ahora lista estas descripciones
en vez de solo los nombres de los equipos.

Con el fix, la misma pregunta rutea correctamente a `news_sentiment` y devuelve la fecha
real (2026-10-29).

## Consecuencias

- Este patrón — describir cada equipo con sus límites explícitos, no solo su nombre — es
  el que hay que seguir al sumar `crypto_alt`: pensar de entrada en qué preguntas podrían
  confundirse con `equity` o `macro` (ej. "precio de Bitcoin" vs. acciones) y anotarlo en
  la descripción antes de que aparezca el bug, no después.
- No resuelve el problema de fondo (un equipo sin la tool correcta puede seguir
  alucinando si el router se equivoca en un caso todavía no anticipado) — eso es
  justamente el trabajo pendiente de guardrails de groundedness, no algo que un mejor
  prompt de routing por sí solo garantice.
- No se agregó un test que cubra específicamente este caso de frontera (equity vs.
  news_sentiment) más allá del test de integración estándar de `news_sentiment` — quedaría
  bien como caso de la futura suite de evaluación (MLflow Evaluate / LangSmith).

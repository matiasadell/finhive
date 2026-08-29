# ADR 0007 — Wrapper defensivo en todas las tools (`safe_tool`)

- **Estado**: aceptado
- **Fecha**: 2026-08-29

## Contexto

Probando el dominio Crypto & Alt (CoinGecko, API pública sin key pero con rate limiting
agresivo para uso anónimo) bajo uso intensivo de testing, apareció un `429 Too Many
Requests` sin capturar dentro de una tool. La excepción se propagó **a través de todo el
grafo jerárquico** — no quedó como una observación que el ReAct worker pudiera ver y
manejar, crasheó directamente la llamada a `graph.invoke()` del top-level supervisor.

En una corrida posterior (sin 429 esta vez, pero probablemente con algún otro fallo
transitorio no capturado), el síntoma fue distinto pero relacionado: el supervisor raíz
respondió *"Ahora que tengo la información sobre el precio actual de Bitcoin, puedo
ayudarte..."* — **sin mencionar el precio en ningún lado**. Ninguna alucinación esta vez
(no inventó un número), pero tampoco una respuesta útil ni una admisión clara de que algo
había fallado.

El problema no es específico de CoinGecko ni de Crypto & Alt: los 5 dominios usan el mismo
patrón (`requests.get(...); response.raise_for_status()`), así que **cualquier** hiccup de
red, rate limit o timeout en **cualquier** tool de **cualquier** dominio podía crashear una
invocación completa del sistema de 5 equipos.

## Decisión

Se agregó `finhive.tools.wrappers.safe_tool`: un decorador que envuelve cualquier función
de tool, atrapa cualquier excepción, y la convierte en un string de error descriptivo en
vez de dejarla propagarse. Ese string queda como observación del ReAct loop — el worker lo
ve como cualquier otro resultado de tool, y puede reintentar con otro input, usar otra
tool, o admitirle al usuario que esa fuente de datos no está disponible ahora.

Se aplicó `tool(safe_tool(func))` (en vez de `tool(func)`) en el `_tools()` de los 5
dominios (`macro`, `equity`, `portfolio_risk`, `news_sentiment`, `crypto_alt`) — cambio
mecánico pero necesario en los 5 lugares, no algo que se pueda centralizar en un solo
punto porque cada dominio arma su propia lista de tools.

Se verificó que `functools.wraps` preserva correctamente `__name__`, docstring y (por
extensión) el schema de argumentos que `langchain_core.tools.tool()` necesita para
construir la tool — sin esto, el wrapper hubiera roto la descripción que ve el LLM.

## Consecuencias

- Cualquier dominio nuevo que se agregue en el futuro tiene que envolver sus tools con
  `safe_tool` desde el principio, no como un parche posterior — es parte del patrón
  estándar junto con "función plana + registro en UC" (ADR 0004).
- No resuelve el caso de la respuesta vacía-pero-no-alucinada observado arriba de forma
  garantizada — eso depende de que el LLM, al ver el mensaje de error, elija comunicarlo
  claramente en vez de dar una respuesta vaga. Mejorar eso es trabajo de guardrails
  (todavía pendiente), no de este wrapper — `safe_tool` evita el crash, no garantiza la
  calidad de la respuesta final.
- CoinGecko sin key tiene rate limiting real y perceptible bajo testing intensivo — a
  diferencia de FRED/SEC EDGAR/yfinance, que no mostraron este problema en el mismo
  volumen de pruebas. Vale la pena tenerlo en cuenta para la demo final: no encadenar
  muchas preguntas de crypto seguidas en poco tiempo.

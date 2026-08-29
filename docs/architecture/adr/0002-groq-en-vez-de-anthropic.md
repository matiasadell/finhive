# ADR 0002 — Groq en vez de Anthropic como proveedor de LLM

- **Estado**: aceptado
- **Fecha**: 2026-08-29
- **Supersede**: parcialmente la decisión #2 de ADR 0001

## Contexto

ADR 0001 eligió Claude (Anthropic) como LLM, registrado como *External Model* en
Databricks Model Serving. Al llegar el momento de generar la key, surgió la pregunta de
si la API de Anthropic tiene costo. Aclaración importante: la API de Anthropic
(console.anthropic.com) es **pay-per-uso y separada** de una suscripción de Claude.ai o
Claude Code — requiere tarjeta cargada, aunque el costo real para un proyecto de
portfolio (tráfico bajo, no producción) suele ser de pocos dólares.

Se evaluó cambiar a Grok (xAI) — también pay-per-token, no resuelve el problema — y a
**Groq** (Groq Inc., el proveedor de inferencia sobre LPUs, no confundir con Grok/xAI),
que sí ofrece un free tier real: sin tarjeta, rate-limited por request/token por minuto
y por día, sirviendo modelos open-weight (Llama 3.3, Llama 3.1, Gemma2, etc.) a muy baja
latencia.

## Decisión

Se reemplaza Anthropic por **Groq** como proveedor de LLM para todos los agentes.

Se verificó que Databricks Model Serving soporta un provider tipo `custom` en External
Models para cualquier endpoint compatible con la API de OpenAI — y la API de Groq
(`https://api.groq.com/openai/v1`) es compatible con ese estándar. Esto preserva
exactamente la misma historia arquitectónica de ADR 0001 (AI Gateway gobernando un
proveedor externo: rate limiting, cost tracking, guardrails, fallback), solo cambia
quién sirve el modelo.

Tiering de modelos (equivalente al Haiku/Sonnet que se había planeado con Anthropic):

| Rol | Modelo Groq |
|---|---|
| Top-level supervisor + síntesis final | `llama-3.3-70b-versatile` |
| Sub-supervisores de dominio | `llama-3.3-70b-versatile` |
| Workers (tool calling simple/extracción) | `llama-3.1-8b-instant` |

## Consecuencias

- `pyproject.toml`: `langchain-anthropic` → `langchain-groq`; se agregó
  `databricks-langchain` (integración oficial `ChatDatabricks`, ausente en el plan
  original — necesaria para que el código llame al endpoint gobernado por AI Gateway en
  vez de a un proveedor directamente).
- `.env.example`/`.env`: `ANTHROPIC_API_KEY` → `GROQ_API_KEY`.
- Al no ser un modelo propietario "de marca" (Claude, GPT), el pitch de storytelling para
  LinkedIn/CV se ajusta: el foco pasa de "qué modelo" a "cómo se gobierna cualquier
  modelo vía AI Gateway" — arguiblemente una historia más fuerte para un rol de AI
  engineer, porque demuestra portabilidad de proveedor real.
- Costo total del proyecto para desarrollo/demo: **$0** en LLM (dentro de los límites del
  free tier de Groq).

# ADR 0008 — Rate limits explícitos de AI Gateway en los 3 endpoints de FinHive

- **Estado**: aceptado
- **Fecha**: 2026-08-29

## Contexto

El usuario, mirando la pantalla de **AI Gateway** en la UI de Databricks, notó que los
endpoints de FinHive (`databricks-meta-llama-3-3-70b-instruct`,
`databricks-meta-llama-3-1-8b-instruct`) no aparecían ahí — en cambio, veía otros
endpoints (`gpt-oss-120b`, `gemma-3-12b`, `bge-large-en`, y `databricks-genie`, este
último ni siquiera un modelo, sino un recurso de Genie Spaces).

Investigado: los 11 endpoints nativos de Foundation Model APIs existen y están `READY`
(confirmado con `databricks serving-endpoints list`), incluidos los tres que usa FinHive.
Esa pantalla de AI Gateway en particular no lista *todos* los endpoints — lista
específicamente los que tienen **políticas de gateway explícitas** configuradas (rate
limits, guardrails), mezclado con otro tipo de recursos (Genie). Consultando
`databricks serving-endpoints get databricks-meta-llama-3-3-70b-instruct`, el campo
`ai_gateway` ya existía pero con **solo** `usage_tracking_config.enabled: true` — el
default que Databricks aplica, sin ningún rate limit ni guardrail explícito.

Esto expuso una brecha real entre lo que el README/ADRs venían afirmando ("Databricks AI
Gateway gobierna el acceso al LLM") y lo efectivamente configurado: la gobernanza era
solo tracking pasivo, no control activo.

## Decisión

Se configuró `rate_limits` explícito (vía `databricks serving-endpoints put-ai-gateway`)
en los 3 endpoints que toca FinHive:

| Endpoint | Rol | Límite |
|---|---|---|
| `databricks-meta-llama-3-3-70b-instruct` | supervisores (raíz + dominio) | 30 calls/usuario/minuto |
| `databricks-meta-llama-3-1-8b-instruct` | workers | 60 calls/usuario/minuto (se llama con más frecuencia) |
| `databricks-gte-large-en` | embeddings (Vector Search, todavía no en uso activo) | 60 calls/usuario/minuto |

`usage_tracking_config.enabled: true` se mantuvo en los tres. Se verificó que el sistema
sigue funcionando normalmente después del cambio (macro supervisor invocado end-to-end,
misma respuesta grounded que antes).

## Consecuencias

- Ahora **sí** hay control activo, no solo tracking pasivo — la afirmación de
  "gobernanza vía AI Gateway" en el README deja de ser aspiracional.
- Los tres endpoints ahora deberían aparecer en la pantalla de AI Gateway de la UI (no
  verificado visualmente, solo confirmado que la config quedó guardada vía API).
- Los límites elegidos (30/60 por minuto) son holgados a propósito — el objetivo acá es
  demostrar el mecanismo, no proteger contra abuso real en un sistema de un solo usuario.
  Si el uso normal empieza a toparse con el límite (preguntas que disparan muchas vueltas
  de iteración, ver ADR 0005), subir el número es la primera palanca antes de sospechar
  de otra cosa.
- Guardrails de contenido (safety, PII) siguen sin configurar acá — eso es parte del
  trabajo pendiente de guardrails en el roadmap general, no de este ADR puntual.

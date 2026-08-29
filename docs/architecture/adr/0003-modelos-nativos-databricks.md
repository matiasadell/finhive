# ADR 0003 — Foundation Model APIs nativos de Databricks en vez de Groq

- **Estado**: aceptado
- **Fecha**: 2026-08-29
- **Supersede**: ADR 0002

## Contexto

ADR 0002 registró Groq como External Model (`custom` provider) en Databricks Model
Serving. Al probarlo con una query real, el endpoint devolvió `Internal Error` de forma
consistente (configuración del custom provider, no investigado a fondo).

En paralelo, revisando el catálogo de modelos disponibles en el workspace (`system.ai.*`),
apareció una duda legítima: varios modelos muestran precio de lista (`$`) en la tabla de
Model Serving, lo que generó preocupación sobre si usarlos en Free Edition podía generar
un cobro real.

## Verificación

Antes de decidir, se verificó en vivo contra el workspace real (no contra documentación
genérica):

1. `databricks serving-endpoints list` mostró que el workspace **ya tiene** provisionados
   y en estado `READY` los endpoints nativos de Foundation Model APIs: GPT OSS 120B/20B,
   Qwen3 Next, Qwen3.5, Llama 4 Maverick, Gemma 3 12B, Llama 3.1 8B Instruct, Llama 3.3
   70B Instruct, más los embeddings GTE Large, BGE Large y Qwen3 Embedding — sin ninguna
   acción de setup adicional.
2. Se hizo una query real contra `databricks-meta-llama-3-3-70b-instruct` (uno de los
   modelos marcados con `$` en la tabla de precios) y respondió correctamente, sin ningún
   error ni aviso de facturación.
3. Free Edition no tiene ningún método de pago asociado a la cuenta — el `$` en la tabla
   de Model Serving es el precio de lista general de Databricks (el mismo que ve un
   workspace pago), no una factura real contra esta cuenta. El control de uso en Free
   Edition es por cuota, no por billing: si se excede la cuota, la request se bloquea con
   un error, nunca se cobra.
4. Los símbolos `—` en esa misma tabla no marcan una categoría "más gratis": corresponden
   simplemente a los modelos de **embeddings** (GTE Large, BGE Large, Qwen3 Embedding),
   que no comparten la misma escala de precio-por-token que los modelos de chat. No hay
   ningún modelo de chat marcado con `—` — todos los de chat muestran `$`, y todos son
   igual de gratuitos en Free Edition.

## Decisión

Se reemplaza Groq por los **Foundation Model APIs nativos de Databricks**:

| Rol | Endpoint | Modelo UC |
|---|---|---|
| Top-level supervisor + síntesis final | `databricks-meta-llama-3-3-70b-instruct` | `system.ai.llama_v3_3_70b_instruct` |
| Sub-supervisores de dominio | `databricks-meta-llama-3-3-70b-instruct` | `system.ai.llama_v3_3_70b_instruct` |
| Workers (tool calling simple/extracción) | `databricks-meta-llama-3-1-8b-instruct` | `system.ai.meta_llama_v3_1_8b_instruct` |
| Embeddings (Databricks Vector Search) | `databricks-gte-large-en` | `system.ai.gte_large_en_v1_5` |

Se eliminó el endpoint `finhive-groq` (roto) y el secret `finhive.groq_api_key` (ya sin
uso), para no dejar recursos sueltos.

## Consecuencias

- **Cero dependencias de key externa para el LLM.** `GROQ_API_KEY` sale de
  `.env`/`.env.example`; el proyecto ya no depende de ninguna cuenta de terceros para el
  modelo de lenguaje.
- `pyproject.toml`: se saca `langchain-groq`; `databricks-langchain` (`ChatDatabricks`)
  cubre la llamada a estos endpoints nativos igual que hubiera cubierto a Groq.
- Se gana, sin costo adicional, un modelo de embeddings nativo (GTE Large) para Databricks
  Vector Search — evita depender de OpenAI embeddings o de un modelo de embeddings externo.
- El pitch de storytelling para LinkedIn/CV se ajusta otra vez: ahora es "un sistema
  multiagente corriendo enteramente sobre la pila nativa de Databricks (Unity Catalog,
  Vector Search, Foundation Model APIs, AI Gateway, Apps) sin ninguna dependencia externa
  de pago" — una historia más limpia y más fácil de reproducir por cualquiera que lea el
  repo, sin necesitar conseguir una cuenta en un tercer proveedor de LLM.
- Costo total del proyecto en LLM + embeddings: **$0**, verificado en vivo, no solo
  supuesto por documentación.

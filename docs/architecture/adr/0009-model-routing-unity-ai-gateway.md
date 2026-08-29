# ADR 0009 — Model routing real vía Unity AI Gateway (`finhive_router`)

- **Estado**: superado por ADR 0010 — la integración que acá quedaba como "pendiente" ya
  está hecha (usando `langchain_openai.ChatOpenAI` en vez de esperar a `databricks-langchain`)
- **Fecha**: 2026-08-29

## Contexto

El usuario, explorando la pantalla **Unity AI Gateway** de Databricks (feature nueva,
GA el 4 de agosto de 2026 — ver [anuncio oficial](https://www.databricks.com/blog/unity-ai-gateway-generally-available)),
quiso crear un **model service** propio con routing entre modelos — el mecanismo real
detrás de "Routing and fallback" que `docs/theory/Summary.pdf` §19 describe como
responsabilidad central de un LLM Gateway.

Esto es distinto de lo que ya existía: los `system.ai.*` `model-services` que aparecen
en esa pantalla son auto-generados por Databricks, uno por cada Foundation Model nativo,
cada uno con `config.routing` vacío (sin routing real, 1:1 con su propio modelo). Los
rate limits que configuramos en ADR 0008 fueron sobre los *serving endpoints* clásicos
(`databricks-meta-llama-3-3-70b-instruct`, etc.), un objeto de API distinto.

## Qué se hizo

Se creó `model-services/workspace.finhive.finhive_router` vía
`databricks ai-gateway create-model-service` / `update-model-service` (comando *Beta*),
con dos destinos y traffic split real:

| Destino | % de tráfico |
|---|---|
| `system.ai.llama_v3_3_70b_instruct` | 70% |
| `system.ai.gpt-oss-120b` | 30% |

El schema del JSON de `config.routing.destinations` no está documentado con el nivel de
detalle necesario en la documentación pública consultada — se descubrió por **iteración
contra los mensajes de validación del propio API** (mismo método que ADR 0002 con el
custom provider de Groq): cada intento devolvía qué campo faltaba, hasta llegar a la
forma completa:

```json
{
  "name": "model-services/system.ai.<modelo>",
  "destination_type": "DESTINATION_TYPE_PAY_PER_TOKEN_FOUNDATION_MODEL",
  "pay_per_token_config": { "model": "models/system.ai.<modelo>" },
  "traffic_percentage": <int>
}
```

Se verificó el routing empíricamente: 6 llamadas de prueba contra
`POST /ai-gateway/mlflow/v1/chat/completions` con `model: "workspace.finhive.finhive_router"`
devolvieron 5 respuestas servidas por `meta-llama-3.3-70b-instruct-121024` y 1 por
`gpt-oss-120b-080525` — consistente con el 70/30 configurado (muestra chica, pero en la
dirección correcta).

## Por qué no se integró a `src/finhive` todavía

Se probó apuntar `ChatDatabricks(endpoint="workspace.finhive.finhive_router")` — el
cliente que usa `finhive.config.settings.get_chat_model` — y falló con
`404 ENDPOINT_NOT_FOUND`. `databricks-langchain` (y el `databricks-sdk` que usa por
debajo) todavía invocan el path clásico `/serving-endpoints/{name}/invocations`, no el
nuevo `/ai-gateway/mlflow/v1/chat/completions` que requieren los `model-services` de
Unity Catalog — coherente con que la librería todavía no absorbió una feature que salió
de GA hace pocas semanas.

**Decisión**: no forzar la integración ahora contra un path de API Beta sin soporte de
librería (arriesgaría estabilidad del sistema por una feature de exploración). El router
queda documentado y verificado como capacidad standalone, invocable directamente vía
`databricks api post /ai-gateway/mlflow/v1/chat/completions`.

## Consecuencias / trabajo futuro

- Cuando `databricks-langchain` soporte `model-services` de Unity Catalog (o se escriba
  un wrapper mínimo de `ChatDatabricks` que pegue directo al path de AI Gateway), cambiar
  `SUPERVISOR_MODEL_ENDPOINT` a `"workspace.finhive.finhive_router"` le da a todo
  supervisor de FinHive resiliencia real a fallos/degradación de un único modelo, sin
  tocar ningún otro código — la abstracción de `get_chat_model` ya está preparada para
  ese swap.
- El patrón de descubrir un schema de API por iteración contra los errores de validación,
  usado acá y en ADR 0002, es reutilizable para cualquier feature Beta de Databricks sin
  documentación pública completa todavía.

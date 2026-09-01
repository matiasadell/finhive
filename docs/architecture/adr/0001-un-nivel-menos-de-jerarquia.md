# ADR 0001 — Un nivel menos de jerarquía que finhive

- **Estado**: aceptado
- **Fecha**: 2026-09-01

## Contexto

finhive (`docs/architecture/adr/finhive-legacy/`) usa una jerarquía de 3 niveles:
supervisor raíz → sub-supervisor por dominio (`langgraph_supervisor.create_supervisor`) →
2-3 workers ReAct por dominio. Cada pregunta de dominio implica, como mínimo, 2 llamadas
LLM de routing (raíz + sub-supervisor) antes de llegar a un worker.

Portfolio Intel tiene 4 dominios (prioritización, reuso/duplicación, value realization,
recomendación de portfolio) y un presupuesto de 1-3 días de hackathon (ver
`prompts/constraints_deadline_process.md`), sin poder invocar el LLM real desde esta
máquina de desarrollo para iterar sobre prompts de sub-supervisor (ver
`prompts/constraints_environment.md`) — cada capa extra de routing es una superficie de
prompt-engineering que solo se puede verificar de verdad en la compu de trabajo.

## Decisión

El supervisor raíz (`graph/top_supervisor.py`) rutea **directo** a un agente ReAct por
dominio (`agents/*.py`), sin un sub-supervisor propio en el medio. Cada agente tiene su
propio toolset determinista (`tools/*.py`) y un system prompt que le prohíbe explícitamente
calcular o inventar un número — solo puede citar lo que una tool ya calculó (ver ADR 0002).

Esto es una simplificación deliberada, no una limitación técnica: el patrón de finhive
(sub-supervisor + workers) sigue siendo válido si un dominio necesitara varios
especialistas distintos (ej. si "value realization" se partiera en "riesgo de costo" vs.
"riesgo de timeline" como workers separados) — no se usó acá porque los 4 dominios de este
proyecto ya son unidades de trabajo chicas y bien delimitadas por su propio toolset.

## Consecuencias

- Una llamada LLM menos por pregunta de dominio (routing raíz + 1 agente, en vez de
  routing raíz + routing sub-supervisor + 1-3 workers) — menos superficie de prompt sin
  verificar en vivo, y menor latencia/cuota una vez desplegado.
- `_TEAM_DESCRIPTIONS` en `top_supervisor.py` sigue siendo el mecanismo de
  desambiguación entre dominios (mismo hallazgo que ADR 0006 de finhive-legacy: nombres
  solos no alcanzan, hacen falta descripciones explícitas con casos de frontera) — no
  cambia con la jerarquía más chata.
- Si este proyecto creciera más allá del hackathon y un dominio necesitara varios
  especialistas, agregar un sub-supervisor a ese dominio específico es un cambio
  localizado (un nuevo `agents/<dominio>/supervisor.py` al estilo finhive), no una
  reescritura del supervisor raíz.

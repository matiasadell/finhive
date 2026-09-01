# ADR 0005 — Dataset sintético construido a propósito, no relleno genérico

- **Estado**: aceptado
- **Fecha**: 2026-09-01

## Contexto

No hay CSVs reales de la empresa (ver `prompts/constraints_data.md`) — hacía falta un
dataset sintético con las columnas exactas de "RUAI Use Case" y "AI Use Case Detail". La
primera versión (`data/synthetic.py`) generaba `business challenge`/`target state` con una
plantilla genérica (`"El equipo de {lob} necesita mejorar {sub_value_chain}..."`) para los
22 casos no-duplicados.

Corriendo `duplication_tools.find_duplicate_use_cases` contra esa primera versión (Task
6), aparecieron **29 pares "duplicados"**, muy por encima de los 4 clusters realmente
diseñados (A-D) — la plantilla compartía tanto léxico entre filas sin relación real que
cualquier par con el mismo `value_chain` scoreaba por encima del umbral de similitud.

## Decisión

Se reemplazó la plantilla por texto de negocio específico y distinto para cada uno de los
22 casos no-duplicados (`_RECORDS` en `data/synthetic.py`, campos `challenge`/`target`),
mientras que los 4 clusters intencionales siguen compartiendo texto con overlap real
(`_DUP_TEXT`). Verificado: con el dataset corregido,
`find_duplicate_use_cases` encuentra exactamente los 4 clusters diseñados, cero falsos
positivos (`tests/unit/test_duplication_tools.py::test_no_false_positives_across_unrelated_cases`).

## Consecuencias

- El dataset sintético no es solo "datos con las columnas correctas" — cada escenario de
  la demo (Task 12) y cada entrada del golden set (Task 13) depende de que el texto/las
  cifras del dataset produzcan la señal correcta cuando se les aplica la lógica
  determinista real, no solo que "parezcan" razonables a simple vista.
- Un dataset sintético con texto de relleno genérico es, en la práctica, un dataset que
  rompe silenciosamente cualquier lógica basada en similitud textual -- vale la pena
  chequearlo corriendo la lógica real contra él antes de darlo por bueno, no solo mirarlo.
- Si se reemplaza este dataset por datos reales de la empresa más adelante, este hallazgo
  aplica igual: texto de `business challenge` genérico/copy-pasteado entre casos de uso
  reales generaría el mismo tipo de falso positivo en `duplication_tools` — no es un
  problema exclusivo de datos sintéticos.

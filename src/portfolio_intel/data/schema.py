"""Contrato de columnas de las dos fuentes reales del AI portfolio.

Todo el resto del paquete importa los nombres de columna desde acá en vez de
hardcodear strings sueltos -- así, cuando el usuario reemplace los CSVs
sintéticos por los reales (mismo esquema, ver `prompts/constraints_data.md`),
solo hay que verificar que los headers calcen con estas constantes.

Dos correcciones de transcripción respecto del texto original pegado por el
usuario (columnas de "AI Use Case Detail"), documentadas acá porque son una
decisión de ingeniería, no un capricho:

1. "use case" aparecía dos veces en la lista pegada (justo después de "phase
   id", y de nuevo después de "sub lob"). Dado el resto del layout (no hay
   ninguna otra columna que luzca como un ID/título distinto ahí), se trata
   como un duplicado de transcripción -- se modela una sola columna "use
   case", que además es la que sirve de join key contra `title` /
   `AI Use Case Name` de RUAI Use Case. Si el CSV real efectivamente trae dos
   columnas separadas ahí, hay que revisar este archivo.
2. "planned opex" aparecía dos veces (una cerca de "prod investment window",
   otra cerca de "planned investment"). Mismo criterio: se modela una sola
   columna "planned opex".

Además, tres typos evidentes del texto pegado por el usuario se corrigieron
sin cambiar el significado: "sub kob" -> "sub lob", "ai kead name" -> "ai
lead name", "ai devekoper name" -> "ai developer name", "secundary impact
type" -> "secondary impact type", "impactedbusiness" -> "impacted business".
"""

from __future__ import annotations

# --- RUAI Use Case (inventario + tracking de aprobación) ---
RUAI_USE_CASE_COLUMNS: list[str] = [
    "AI Use Case Name",
    "count",
    "use case id",
    "title",
    "current approved lifecycle",
    "requested lifecycle stage",
    "ruai approval track",
    "overall use case review status",
    "submission status detail",
    "business owner",
    "technical owner",
    "technology owner",
    "type of ai",
    "technology platform",
]

# --- AI Use Case Detail (value/KPI, inversión, impacto, contexto de negocio) ---
USE_CASE_DETAIL_COLUMNS: list[str] = [
    "phase id",
    "use case",
    "use case submission date",
    "lob",
    "sub lob",
    "use case submitter",
    "assigned architect",
    "ai lead name",
    "use case status",
    "current stage name",
    "timing to get to the next stage",
    "technical lead",
    "ai developer name",
    "business challenge",
    "target state",
    "comments",
    "confidence level",
    "confidence explanation",
    "value return begins in",
    "value return plateaus in",
    "prod investment window",
    "planned opex",
    "scalability",
    "current user",
    "target user",
    "insight learned or barriers",
    "accuracy of the model",
    "procurement required",
    "max impact",
    "min impact",
    "planned investment",
    "projected total investment",
    "primary impact type",
    "secondary impact type",
    "focus area",
    "value chain",
    "sub value chain",
    "domain",
    "geography",
    "impacted business",
    "impacted business detail",
    "products",
]

# --- Join key entre los dos archivos ---
# RUAI no tiene una columna de detalle único aparte de "use case id"/"title";
# AI Use Case Detail no tiene columna de ID, solo el título en "use case". El
# join real, entonces, es por coincidencia exacta de texto entre
# RUAI["title"] y DETAIL["use case"] -- por eso el generador sintético
# (`synthetic.py`) mantiene ambos strings idénticos por diseño, y cualquier
# fuente real tiene que respetar esa misma convención para que el join ande.
RUAI_JOIN_COLUMN = "title"
DETAIL_JOIN_COLUMN = "use case"

# --- Vocabularios controlados usados por el generador sintético y las tools ---
# No son parte del "contrato" con el CSV real (esas columnas son texto libre
# en la fuente real) -- viven acá porque son el vocabulario que el generador
# sintético (Task 3) y las tools deterministas (Task 5-8) comparten.
LIFECYCLE_STAGES: list[str] = [
    "Ideation",
    "Intake Review",
    "Pilot",
    "Limited Production",
    "Full Production",
    "On Hold",
]
CONFIDENCE_LEVELS: list[str] = ["Low", "Medium", "High"]
SCALABILITY_LEVELS: list[str] = ["Low", "Medium", "High"]
IMPACT_TYPES: list[str] = [
    "Cost Reduction",
    "Revenue Growth",
    "Risk Reduction",
    "Customer Experience",
    "Employee Productivity",
    "Regulatory Compliance",
]

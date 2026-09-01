from __future__ import annotations

# Columnas exactas de las 2 fuentes reales. "use case"/"planned opex"
# aparecían duplicadas en el texto original pegado -- se modelan una sola vez.

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

# Join por coincidencia exacta de texto: RUAI["title"] <-> DETAIL["use case"].
RUAI_JOIN_COLUMN = "title"
DETAIL_JOIN_COLUMN = "use case"

# Vocabulario compartido por el generador sintético y las tools.
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

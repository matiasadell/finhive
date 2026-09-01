# Generador de dataset sintético (30 casos de uso, determinístico) -- ver
# data/sample_docs/README.md para el detalle de los escenarios construidos.

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from portfolio_intel.data.schema import DETAIL_JOIN_COLUMN, RUAI_JOIN_COLUMN

_SAMPLE_DOCS_DIR = Path(__file__).resolve().parents[3] / "data" / "sample_docs"

# tier -> (min_impact $, max_impact $, confidence, scalability)
_TIER_PROFILE = {
    "scale": (400_000, 1_500_000, "High", "High"),
    "monitor": (100_000, 400_000, "Medium", "Medium"),
    "at_risk": (150_000, 500_000, "Low", "Medium"),
    "discontinue": (20_000, 80_000, "Low", "Low"),
}

_SUBMISSION_DATE_BY_STAGE = {
    "Full Production": date(2024, 8, 1),
    "Limited Production": date(2025, 1, 15),
    "Pilot": date(2025, 6, 1),
    "Intake Review": date(2026, 3, 1),
    "Ideation": date(2026, 5, 1),
    "On Hold": date(2025, 9, 1),
}

# Texto compartido entre pares casi-duplicados: mismo problema de negocio
# descrito con palabras superpuestas, a propósito, para que la detección de
# duplicados (Task 6) los encuentre por overlap textual real, no por metadata.
_DUP_TEXT = {
    "A": (
        "Los adjusters de {region} pasan demasiado tiempo respondiendo "
        "preguntas repetitivas de status de claim por telefono, alargando el "
        "tiempo de resolucion y bajando la satisfaccion del cliente.",
        "Un asistente conversacional que responda el status del claim en "
        "tiempo real, liberando tiempo de los adjusters para casos complejos.",
    ),
    "B": (
        "Los analistas de SIU revisan manualmente patrones de claims "
        "sospechosos, un proceso lento que no escala con el volumen actual "
        "de siniestros.",
        "Un modelo que marque automaticamente patrones de claims "
        "sospechosos para priorizar la revision manual del equipo de SIU.",
    ),
    "C": (
        "El equipo de reclutamiento revisa manualmente cientos de resumes "
        "por posicion abierta, un cuello de botella que alarga el time-to-hire.",
        "Una herramienta que preseleccione candidatos automaticamente en "
        "base al match entre el resume y los requisitos del puesto.",
    ),
    "D": (
        "Las ofertas de renovacion de poliza son genericas y no reflejan el "
        "perfil real del cliente, bajando la tasa de conversion en renovaciones.",
        "Un modelo que recomiende la oferta de renovacion mas relevante para "
        "cada cliente en base a su historial y perfil de riesgo.",
    ),
}

# Cada registro: id, title, lob, value_chain, sub_value_chain, type_of_ai,
# stage, tier, dup_group (o None), y una nota de riesgo/barrera para los
# casos "at_risk" (o None para el resto).
_RECORDS: list[dict] = [
    dict(id="UC-001", title="AI-Powered Claims Triage", lob="Claims",
         value_chain="Claims", sub_value_chain="Adjudication",
         type_of_ai="Predictive ML", stage="Full Production", tier="scale",
         challenge=(
             "Los examinadores de claims de auto pasan horas revisando "
             "manualmente fotos de danos y estimaciones de repuestos antes "
             "de aprobar un pago, generando cuellos de botella en la cola "
             "de adjudicacion."
         ),
         target=(
             "Clasificar automaticamente la severidad del dano a partir de "
             "fotos para acelerar la aprobacion de claims de bajo riesgo."
         )),
    dict(id="UC-002", title="Automated FNOL Intake Assistant", lob="Claims",
         value_chain="Claims", sub_value_chain="First Notice of Loss",
         type_of_ai="NLP/Classification", stage="Limited Production", tier="scale",
         challenge=(
             "El formulario inicial de reporte de siniestro (FNOL) obliga "
             "al asegurado a completar campos tecnicos que no entiende, "
             "generando datos incompletos que hay que corregir despues."
         ),
         target=(
             "Guiar al asegurado con un asistente conversacional que "
             "complete el FNOL en lenguaje natural y valide los datos en "
             "el momento."
         )),
    dict(id="UC-003", title="Underwriting Risk Scoring Model", lob="Underwriting",
         value_chain="Underwriting", sub_value_chain="Risk Selection",
         type_of_ai="Predictive ML", stage="Full Production", tier="scale",
         challenge=(
             "Los suscriptores de polizas de auto revisan cada solicitud "
             "nueva a mano contra decenas de reglas de riesgo, sin poder "
             "priorizar cuales requieren atencion urgente."
         ),
         target=(
             "Puntuar automaticamente el nivel de riesgo de cada solicitud "
             "nueva para que los suscriptores prioricen su cola de trabajo."
         )),
    dict(id="UC-004", title="Fraud Anomaly Detection Engine", lob="Fraud & SIU",
         value_chain="Fraud", sub_value_chain="Detection",
         type_of_ai="Predictive ML", stage="Limited Production", tier="scale",
         challenge=(
             "El volumen de siniestros supera la capacidad del equipo de "
             "SIU para revisar manualmente cada uno en busca de indicios "
             "de fraude."
         ),
         target=(
             "Marcar automaticamente los siniestros con mayor probabilidad "
             "de fraude para que el equipo de SIU enfoque su revision ahi "
             "primero."
         )),
    dict(id="UC-005", title="Auto Insurance Pricing Optimization", lob="Actuarial",
         value_chain="Pricing & Actuarial", sub_value_chain="Pricing",
         type_of_ai="Optimization/Rules Engine", stage="Limited Production", tier="scale",
         challenge=(
             "Las tarifas de polizas de auto se actualizan trimestralmente "
             "con un proceso manual de hojas de calculo que no incorpora "
             "senales de riesgo recientes."
         ),
         target=(
             "Optimizar la tarifa de cada poliza de auto de forma continua "
             "incorporando senales de riesgo actualizadas."
         )),
    dict(id="UC-006", title="Commercial Underwriting Submission Scoring", lob="Underwriting",
         value_chain="Underwriting", sub_value_chain="Submission Intake",
         type_of_ai="Predictive ML", stage="Full Production", tier="scale",
         challenge=(
             "Las solicitudes de polizas comerciales llegan en formatos "
             "heterogeneos (PDF, email, portal) y el equipo de intake las "
             "clasifica manualmente antes de asignarlas a un suscriptor."
         ),
         target=(
             "Clasificar y enrutar automaticamente cada solicitud "
             "comercial entrante al suscriptor correcto segun el tipo de "
             "riesgo."
         )),

    # Cluster A: chatbot de status de claims, construido dos veces por region
    dict(id="UC-007", title="Claims Status Chatbot (East Region)", lob="Claims",
         value_chain="Claims", sub_value_chain="Customer Communication",
         type_of_ai="Generative AI", stage="Pilot", tier="monitor", dup_group="A",
         dup_region="la region Este"),
    dict(id="UC-008", title="Virtual Claims Assistant (West Region)", lob="Claims",
         value_chain="Claims", sub_value_chain="Customer Communication",
         type_of_ai="Generative AI", stage="Pilot", tier="monitor", dup_group="A",
         dup_region="la region Oeste"),

    # Cluster B: deteccion de fraude, SIU vs Underwriting
    dict(id="UC-009", title="Suspicious Claims Pattern Detector", lob="Fraud & SIU",
         value_chain="Fraud", sub_value_chain="Investigation",
         type_of_ai="Predictive ML", stage="Pilot", tier="monitor", dup_group="B",
         dup_region="SIU"),
    dict(id="UC-010", title="Underwriting Fraud Signal Flagging Tool", lob="Underwriting",
         value_chain="Fraud", sub_value_chain="Investigation",
         type_of_ai="Predictive ML", stage="Ideation", tier="discontinue", dup_group="B",
         dup_region="Underwriting"),

    # Cluster C: screening de resumes, HR vs IT Recruiting
    dict(id="UC-011", title="AI Resume Screening Assistant (HR)", lob="HR",
         value_chain="HR", sub_value_chain="Talent Acquisition",
         type_of_ai="NLP/Classification", stage="Pilot", tier="at_risk", dup_group="C",
         dup_region="HR", risk_note=(
             "El modelo de matching todavia no supera el 55% de accuracy en "
             "validacion, muy por debajo del umbral de 80% definido para pasar "
             "a produccion."
         )),
    dict(id="UC-012", title="Candidate Matching Tool (IT Recruiting)", lob="IT Operations",
         value_chain="HR", sub_value_chain="Talent Acquisition",
         type_of_ai="NLP/Classification", stage="Ideation", tier="discontinue", dup_group="C",
         dup_region="IT Recruiting"),

    # Cluster D: personalizacion de renovaciones, Marketing
    dict(id="UC-013", title="Personalized Policy Recommendation Engine", lob="Marketing",
         value_chain="Marketing", sub_value_chain="Personalization",
         type_of_ai="Predictive ML", stage="Limited Production", tier="monitor", dup_group="D",
         dup_region="el canal digital"),
    dict(id="UC-014", title="Next-Best-Offer Model for Renewals", lob="Marketing",
         value_chain="Marketing", sub_value_chain="Personalization",
         type_of_ai="Predictive ML", stage="Pilot", tier="monitor", dup_group="D",
         dup_region="el canal de call center"),

    # At-risk / off-track de value realization
    dict(id="UC-015", title="Automated Policy Document Summarizer", lob="Underwriting",
         value_chain="Underwriting", sub_value_chain="Documentation",
         type_of_ai="Generative AI", stage="Limited Production", tier="at_risk",
         challenge=(
             "Los suscriptores dedican horas a resumir polizas comerciales "
             "extensas antes de una renovacion, un trabajo repetitivo que "
             "retrasa la decision final."
         ),
         target=(
             "Generar automaticamente un resumen ejecutivo de cada poliza "
             "comercial antes de la revision de renovacion."
         ),
         risk_note=(
             "El costo de cómputo de inferencia terminó siendo 3x lo "
             "presupuestado; el caso ya está en producción limitada pero el "
             "retorno neto sigue negativo."
         )),
    dict(id="UC-016", title="Predictive Churn Model for Renewals", lob="Marketing",
         value_chain="Marketing", sub_value_chain="Retention",
         type_of_ai="Predictive ML", stage="Pilot", tier="at_risk",
         challenge=(
             "Un porcentaje creciente de clientes no renueva su poliza sin "
             "que el equipo de marketing tenga anticipacion suficiente "
             "para intervenir."
         ),
         target=(
             "Predecir con anticipacion que clientes tienen alto riesgo de "
             "no renovar para poder ofrecerles una intervencion de "
             "retencion."
         ),
         risk_note=(
             "La calidad de los datos históricos de renovación tiene huecos "
             "significativos en dos de los cuatro mercados objetivo, "
             "retrasando la validación del modelo."
         )),
    dict(id="UC-017", title="Generative AI Claims Letter Drafting", lob="Claims",
         value_chain="Claims", sub_value_chain="Correspondence",
         type_of_ai="Generative AI", stage="Pilot", tier="at_risk",
         challenge=(
             "Redactar cartas de resolucion de claims a medida para cada "
             "asegurado consume tiempo del equipo de claims que podria "
             "dedicarse a casos complejos."
         ),
         target=(
             "Generar un primer borrador de carta de resolucion de claims "
             "que el equipo solo tenga que revisar y ajustar."
         ),
         risk_note=(
             "Revisión legal encontró errores de tono/precisión en el 12% de "
             "las cartas generadas; el piloto está pausado hasta resolver "
             "accuracy."
         )),
    dict(id="UC-018", title="Actuarial Reserve Estimation Assistant", lob="Actuarial",
         value_chain="Pricing & Actuarial", sub_value_chain="Reserving",
         type_of_ai="Predictive ML", stage="Limited Production", tier="at_risk",
         challenge=(
             "El equipo actuarial calcula reservas de siniestros "
             "pendientes con hojas de calculo que no escalan al volumen "
             "actual de la cartera."
         ),
         target=(
             "Asistir el calculo de reservas de siniestros pendientes con "
             "un modelo que incorpore el historial completo de la cartera."
         ),
         risk_note=(
             "Compliance regulatorio todavía no aprobó el modelo para todos "
             "los estados donde opera la aseguradora, bloqueando el "
             "despliegue completo prometido para este trimestre."
         )),
    dict(id="UC-019", title="IT Ops Incident Triage Bot", lob="IT Operations",
         value_chain="IT Operations", sub_value_chain="Infrastructure",
         type_of_ai="Predictive ML", stage="Pilot", tier="at_risk",
         challenge=(
             "Los incidentes de infraestructura de TI se triagean "
             "manualmente por orden de llegada, sin priorizar los que "
             "afectan sistemas criticos de cara al cliente."
         ),
         target=(
             "Priorizar automaticamente los incidentes de infraestructura "
             "segun su impacto real en sistemas criticos."
         ),
         risk_note=(
             "El equipo de plataforma que iba a mantener el bot fue "
             "reasignado a otra iniciativa; no hay owner técnico activo hace "
             "dos meses."
         )),

    # Candidatos a discontinuar
    dict(id="UC-020", title="Legacy Document OCR Cleanup Tool", lob="IT Operations",
         value_chain="IT Operations", sub_value_chain="DevOps",
         type_of_ai="Computer Vision", stage="Ideation", tier="discontinue",
         challenge=(
             "Documentos legacy escaneados en distintos formatos "
             "dificultan que las herramientas internas los procesen de "
             "forma consistente."
         ),
         target=(
             "Normalizar automaticamente documentos legacy escaneados a un "
             "formato unico y consistente."
         )),
    dict(id="UC-021", title="Employee Sentiment Survey Analyzer", lob="HR",
         value_chain="HR", sub_value_chain="Employee Experience",
         type_of_ai="NLP/Classification", stage="Ideation", tier="discontinue",
         challenge=(
             "Las encuestas de clima interno generan cientos de "
             "comentarios abiertos que RRHH no llega a leer ni categorizar "
             "a tiempo."
         ),
         target=(
             "Categorizar y resumir automaticamente los comentarios "
             "abiertos de las encuestas de clima para RRHH."
         )),
    dict(id="UC-022", title="Marketing Copy A/B Test Generator", lob="Marketing",
         value_chain="Marketing", sub_value_chain="Content",
         type_of_ai="Generative AI", stage="Ideation", tier="discontinue",
         challenge=(
             "El equipo de marketing prueba manualmente variantes de copy "
             "publicitario, un proceso lento que limita cuantas campanas "
             "pueden testear por trimestre."
         ),
         target=(
             "Generar variantes de copy publicitario para acelerar las "
             "pruebas A/B de campanas de marketing."
         )),
    dict(id="UC-023", title="Vendor Invoice Matching Bot", lob="IT Operations",
         value_chain="IT Operations", sub_value_chain="Finance Ops",
         type_of_ai="RPA + AI", stage="Ideation", tier="discontinue",
         challenge=(
             "Conciliar facturas de proveedores contra ordenes de compra "
             "se hace a mano en el equipo de finance ops, un proceso "
             "propenso a errores."
         ),
         target=(
             "Conciliar automaticamente facturas de proveedores contra "
             "ordenes de compra para reducir el trabajo manual de finance "
             "ops."
         )),
    dict(id="UC-024", title="Internal FAQ Chatbot for Underwriters", lob="Underwriting",
         value_chain="Underwriting", sub_value_chain="Enablement",
         type_of_ai="Generative AI", stage="On Hold", tier="discontinue",
         challenge=(
             "Los suscriptores nuevos hacen las mismas preguntas repetidas "
             "sobre politicas internas a sus colegas senior, "
             "interrumpiendo su trabajo."
         ),
         target=(
             "Responder preguntas frecuentes de suscriptores nuevos sobre "
             "politicas internas sin depender de un colega senior."
         )),

    # Relleno "monitor" -- realismo de portfolio, sin escenario especial
    dict(id="UC-025", title="Commercial Lines Submission Triage", lob="Underwriting",
         value_chain="Underwriting", sub_value_chain="Submission Intake",
         type_of_ai="NLP/Classification", stage="Pilot", tier="monitor",
         challenge=(
             "El equipo de lineas comerciales recibe sumisiones de "
             "corredores con informacion incompleta que hay que pedir de "
             "vuelta antes de poder cotizar."
         ),
         target=(
             "Detectar automaticamente que informacion falta en una "
             "sumision comercial entrante antes de asignarla a un "
             "suscriptor."
         )),
    dict(id="UC-026", title="Customer Self-Service Portal NLU", lob="Customer Service",
         value_chain="Customer Service", sub_value_chain="Self-Service Portal",
         type_of_ai="NLP/Classification", stage="Limited Production", tier="monitor",
         challenge=(
             "Los clientes que usan el portal de autoservicio abandonan la "
             "sesion cuando no encuentran la opcion que buscan entre los "
             "menus actuales."
         ),
         target=(
             "Entender la intencion del cliente en lenguaje natural dentro "
             "del portal de autoservicio y llevarlo directo a la opcion "
             "correcta."
         )),
    dict(id="UC-027", title="Telematics Driving Score Model", lob="Actuarial",
         value_chain="Pricing & Actuarial", sub_value_chain="Telematics",
         type_of_ai="Predictive ML", stage="Pilot", tier="monitor",
         challenge=(
             "Los datos crudos de telematica de manejo se acumulan sin que "
             "el equipo actuarial tenga forma sistematica de traducirlos "
             "en un score de riesgo."
         ),
         target=(
             "Convertir los datos crudos de telematica de manejo en un "
             "score de riesgo de conduccion individual."
         )),
    dict(id="UC-028", title="Claims Subrogation Opportunity Finder", lob="Claims",
         value_chain="Claims", sub_value_chain="Subrogation",
         type_of_ai="Predictive ML", stage="Pilot", tier="monitor",
         challenge=(
             "El equipo de subrogacion revisa manualmente cada claim "
             "cerrado para detectar oportunidades de recupero, un proceso "
             "que no escala con el volumen."
         ),
         target=(
             "Identificar automaticamente que claims cerrados tienen una "
             "oportunidad de subrogacion real que vale la pena perseguir."
         )),
    dict(id="UC-029", title="Agent Call Summarization Assistant", lob="Customer Service",
         value_chain="Customer Service", sub_value_chain="Contact Center",
         type_of_ai="Generative AI", stage="Limited Production", tier="monitor",
         challenge=(
             "Los agentes del call center escriben a mano el resumen de "
             "cada llamada despues de cortar, un paso que alarga el "
             "tiempo entre llamadas."
         ),
         target=(
             "Generar automaticamente el resumen de cada llamada del call "
             "center a partir de la transcripcion."
         )),
    dict(id="UC-030", title="HR Onboarding Document Automation", lob="HR",
         challenge=(
             "El onboarding de nuevos empleados requiere completar y "
             "archivar manualmente una docena de documentos distintos en "
             "sistemas separados."
         ),
         target=(
             "Automatizar la recoleccion y archivo de los documentos de "
             "onboarding de nuevos empleados en un solo flujo."
         ),
         value_chain="HR", sub_value_chain="Onboarding",
         type_of_ai="RPA + AI", stage="Pilot", tier="monitor"),
]

_TODAY = date(2026, 9, 1)


def _investment_figures(tier: str, index: int) -> dict:
    min_impact, max_impact, confidence, scalability = _TIER_PROFILE[tier]
    # Jitter determinístico (no random) para que los montos no queden todos
    # idénticos dentro de un tier, sin perder reproducibilidad.
    jitter = (index * 37) % 100 / 100.0
    max_impact_val = round(min_impact + (max_impact - min_impact) * jitter, -3)
    min_impact_val = round(max_impact_val * 0.4, -3)
    planned_investment = round(max_impact_val * 0.35, -3)
    if tier == "at_risk":
        # El sobre-costo real es la señal que Task 7 tiene que detectar.
        projected_total_investment = round(planned_investment * 2.4, -3)
    else:
        projected_total_investment = round(planned_investment * 1.15, -3)
    planned_opex = round(projected_total_investment * 0.15, -3)
    return {
        "confidence_level": confidence,
        "scalability": scalability,
        "min_impact": min_impact_val,
        "max_impact": max_impact_val,
        "planned_investment": planned_investment,
        "projected_total_investment": projected_total_investment,
        "planned_opex": planned_opex,
    }


def _value_return_dates(stage: str, submission: date, tier: str) -> dict:
    prod_investment_window_months = 6 if stage in ("Full Production", "Limited Production") else 9
    begins = submission + timedelta(days=prod_investment_window_months * 30)
    if tier == "at_risk":
        # A propósito: la fecha de inicio de valor ya pasó (relativa a hoy),
        # pero el stage todavía no llegó a producción -- eso es lo que hace
        # que Task 7 lo marque at_risk/off_track por timeline, no solo costo.
        begins = _TODAY - timedelta(days=30)
    plateaus = begins + timedelta(days=270)
    return {
        "prod_investment_window": f"{prod_investment_window_months} months",
        "value_return_begins_in": begins.isoformat(),
        "value_return_plateaus_in": plateaus.isoformat(),
    }


def generate_use_cases() -> list[dict]:
    records = []
    for i, rec in enumerate(_RECORDS):
        stage = rec["stage"]
        submission = _SUBMISSION_DATE_BY_STAGE[stage]
        figures = _investment_figures(rec["tier"], i)
        dates = _value_return_dates(stage, submission, rec["tier"])

        dup_group = rec.get("dup_group")
        if dup_group:
            # Casos de un mismo cluster comparten texto (con overlap real a
            # propósito, ver `_DUP_TEXT`) -- es justamente la señal que
            # `duplication_tools.find_duplicate_use_cases` tiene que
            # encontrar.
            challenge_tpl, target_tpl = _DUP_TEXT[dup_group]
            business_challenge = challenge_tpl.format(region=rec.get("dup_region", ""))
            target_state = target_tpl.format(region=rec.get("dup_region", ""))
        else:
            # Todo caso no-duplicado trae su propio texto específico
            # (`challenge`/`target` en `_RECORDS`) -- a propósito, no una
            # plantilla genérica: un texto genérico compartido generaba
            # falsos positivos de duplicación entre casos sin relación real
            # (mismo léxico repetido en cada fila), detectado corriendo
            # `duplication_tools.find_duplicate_use_cases` sobre una versión
            # anterior de este dataset.
            business_challenge = rec["challenge"]
            target_state = rec["target"]

        risk_note = rec.get("risk_note", "")

        records.append(
            {
                "id": rec["id"],
                "title": rec["title"],
                "lob": rec["lob"],
                "sub_lob": rec["sub_value_chain"],
                "value_chain": rec["value_chain"],
                "sub_value_chain": rec["sub_value_chain"],
                "domain": rec["value_chain"],
                "focus_area": rec["value_chain"],
                "type_of_ai": rec["type_of_ai"],
                "current_stage_name": stage,
                "tier": rec["tier"],
                "dup_group": dup_group,
                "use_case_submission_date": submission.isoformat(),
                "business_challenge": business_challenge,
                "target_state": target_state,
                "insight_learned_or_barriers": risk_note,
                **figures,
                **dates,
            }
        )
    return records


def _project_to_ruai(records: list[dict]) -> pd.DataFrame:
    stage_to_track = {
        "Full Production": "Standard",
        "Limited Production": "Standard",
        "Pilot": "Standard",
        "Intake Review": "Expedited",
        "Ideation": "Standard",
        "On Hold": "High-Risk Review",
    }
    stage_to_status = {
        "Full Production": "Approved",
        "Limited Production": "Approved",
        "Pilot": "Conditionally Approved",
        "Intake Review": "Pending Review",
        "Ideation": "Pending Review",
        "On Hold": "On Hold",
    }
    tech_platform_by_ai_type = {
        "Generative AI": "Azure OpenAI",
        "Predictive ML": "Databricks (native FMAPI)",
        "NLP/Classification": "Databricks (native FMAPI)",
        "Computer Vision": "AWS SageMaker",
        "Optimization/Rules Engine": "Internal ML Platform",
        "RPA + AI": "Third-party SaaS (Vendor X)",
    }
    rows = []
    for r in records:
        stage = r["current_stage_name"]
        rows.append(
            {
                "AI Use Case Name": r["title"],
                "count": 1,
                "use case id": r["id"],
                "title": r["title"],
                "current approved lifecycle": stage,
                "requested lifecycle stage": stage,
                "ruai approval track": stage_to_track[stage],
                "overall use case review status": stage_to_status[stage],
                "submission status detail": f"{stage_to_status[stage]} as of {r['use_case_submission_date']}",
                "business owner": f"{r['lob']} Business Owner",
                "technical owner": f"{r['lob']} Technical Lead",
                "technology owner": "Enterprise AI Platform Team",
                "type of ai": r["type_of_ai"],
                "technology platform": tech_platform_by_ai_type[r["type_of_ai"]],
            }
        )
    return pd.DataFrame(rows, columns=[
        "AI Use Case Name", "count", "use case id", "title",
        "current approved lifecycle", "requested lifecycle stage",
        "ruai approval track", "overall use case review status",
        "submission status detail", "business owner", "technical owner",
        "technology owner", "type of ai", "technology platform",
    ])


def _project_to_detail(records: list[dict]) -> pd.DataFrame:
    rows = []
    for i, r in enumerate(records):
        confidence_low = r["confidence_level"] == "Low"
        rows.append(
            {
                "phase id": f"PH-{i + 1:03d}",
                "use case": r["title"],
                "use case submission date": r["use_case_submission_date"],
                "lob": r["lob"],
                "sub lob": r["sub_lob"],
                "use case submitter": f"{r['lob']} Business Owner",
                "assigned architect": "Enterprise AI Platform Team",
                "ai lead name": f"{r['lob']} AI Lead",
                "use case status": "Active" if r["tier"] != "discontinue" else "At Risk",
                "current stage name": r["current_stage_name"],
                "timing to get to the next stage": "60 days" if r["tier"] != "discontinue" else "Unclear",
                "technical lead": f"{r['lob']} Technical Lead",
                "ai developer name": "Enterprise AI Platform Team",
                "business challenge": r["business_challenge"],
                "target state": r["target_state"],
                "comments": (
                    "Posible overlap con otra iniciativa del portfolio -- revisar."
                    if r["dup_group"] else ""
                ),
                "confidence level": r["confidence_level"],
                "confidence explanation": (
                    "Piloto todavía no validó accuracy/adopción suficiente."
                    if confidence_low else
                    "Resultados de piloto/producción consistentes con lo proyectado."
                ),
                "value return begins in": r["value_return_begins_in"],
                "value return plateaus in": r["value_return_plateaus_in"],
                "prod investment window": r["prod_investment_window"],
                "planned opex": r["planned_opex"],
                "scalability": r["scalability"],
                "current user": r["lob"] if r["current_stage_name"] != "Ideation" else "N/A (pre-pilot)",
                "target user": r["lob"],
                "insight learned or barriers": r["insight_learned_or_barriers"],
                "accuracy of the model": "N/A" if r["type_of_ai"] == "Optimization/Rules Engine" else (
                    "58%" if confidence_low else "87%"
                ),
                "procurement required": "Yes" if r["type_of_ai"] in (
                    "Computer Vision", "RPA + AI"
                ) else "No",
                "max impact": r["max_impact"],
                "min impact": r["min_impact"],
                "planned investment": r["planned_investment"],
                "projected total investment": r["projected_total_investment"],
                "primary impact type": "Cost Reduction",
                "secondary impact type": "Customer Experience",
                "focus area": r["focus_area"],
                "value chain": r["value_chain"],
                "sub value chain": r["sub_value_chain"],
                "domain": r["domain"],
                "geography": "US",
                "impacted business": r["lob"],
                "impacted business detail": f"{r['lob']} operations, {r['sub_value_chain']}",
                "products": "N/A (Internal)" if r["lob"] in ("IT Operations", "HR") else "Auto & Home Insurance",
            }
        )
    return pd.DataFrame(rows, columns=[
        "phase id", "use case", "use case submission date", "lob", "sub lob",
        "use case submitter", "assigned architect", "ai lead name",
        "use case status", "current stage name",
        "timing to get to the next stage", "technical lead",
        "ai developer name", "business challenge", "target state", "comments",
        "confidence level", "confidence explanation", "value return begins in",
        "value return plateaus in", "prod investment window", "planned opex",
        "scalability", "current user", "target user",
        "insight learned or barriers", "accuracy of the model",
        "procurement required", "max impact", "min impact",
        "planned investment", "projected total investment",
        "primary impact type", "secondary impact type", "focus area",
        "value chain", "sub value chain", "domain", "geography",
        "impacted business", "impacted business detail", "products",
    ])


def write_csvs(output_dir: Path | None = None) -> tuple[Path, Path]:
    output_dir = output_dir or _SAMPLE_DOCS_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    records = generate_use_cases()
    ruai_df = _project_to_ruai(records)
    detail_df = _project_to_detail(records)

    assert set(ruai_df[RUAI_JOIN_COLUMN]) == set(detail_df[DETAIL_JOIN_COLUMN]), (
        "El join key entre RUAI y Detail no matchea -- revisar generate_use_cases()."
    )

    ruai_path = output_dir / "rua_use_case_inventory.csv"
    detail_path = output_dir / "ai_use_case_detail.csv"
    ruai_df.to_csv(ruai_path, index=False)
    detail_df.to_csv(detail_path, index=False)
    return ruai_path, detail_path


if __name__ == "__main__":
    written = write_csvs()
    for path in written:
        print(f"wrote {path}")

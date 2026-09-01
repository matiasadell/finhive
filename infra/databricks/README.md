# infra/databricks/

Sin scripts de setup en este pase: no se provisionó ningún workspace real ni se tocó
infraestructura de Databricks desde esta máquina de desarrollo (ver
`prompts/non_goals.md` — explícitamente fuera de alcance de este pase, y sin conexión a
Databricks para probarlo igual, ver `prompts/constraints_environment.md`).

Pendiente para cuando se corra contra Databricks real (compu de trabajo, ver
`README.md` → "Para correr contra Databricks real"): un schema `workspace.portfolio_intel`
en Unity Catalog y las dos tablas Delta que espera `DatabricksDeltaStore`
(`src/portfolio_intel/data/store.py`, ver ADR 0003) —
`rua_use_case_inventory`/`ai_use_case_detail`, mismo esquema que los CSVs sintéticos
(`src/portfolio_intel/data/schema.py`).

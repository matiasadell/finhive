# app/

Sin frontend en este pase, a propósito: el equipo del usuario construye la UI por su
cuenta, directo contra el paquete Python `portfolio_intel` (ver
`prompts/non_goals.md` y `prompts/constraints_tech_stack.md`) — no un servidor HTTP ni
una app de Databricks Apps escrita acá. `build_top_supervisor()`
(`portfolio_intel.graph`) y `render_executive_report()`
(`portfolio_intel.reporting.executive_report`) son los dos puntos de entrada que un
frontend externo integraría.

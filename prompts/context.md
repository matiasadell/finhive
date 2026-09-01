# Context

No external reference material (no theory PDFs, no class content) applies here —
`context/` stays empty. The relevant prior art is the sibling project in this same
repo:

- `src/finhive/` (on `main`) — read for architectural patterns to mirror: hierarchical
  supervisor composition (`src/finhive/graph/top_supervisor.py`), a domain
  sub-supervisor + ReAct workers (`src/finhive/agents/macro/`), the defensive tool
  wrapper (`src/finhive/tools/wrappers.py`), guardrail nodes
  (`src/finhive/guardrails/`), and the ADR convention (`docs/architecture/adr/`).
  Treat this as a pattern reference, not a dependency — Portfolio Intel does not
  import from `finhive`, and every prompt/tool/data model is written fresh for this
  domain.
- The two real column schemas the user pasted (see `prompts/constraints_data.md`)
  are the only data reference; there is no sample of real rows, so realistic
  synthetic data has to be generated from the schema plus domain knowledge of what
  plausible AI portfolio governance data looks like (e.g. plausible LOBs, use-case
  names, confidence levels, investment ranges, stage names).
- A previous, abandoned attempt at this same challenge exists at
  `git branch hackathon-insurance-portfolio` in this repo — it pivoted to a generic
  "insurance business initiatives" domain, which the user confirmed was the wrong
  domain. It is **not** reference material to build on; ignore its content entirely
  (do not read it for design ideas) and do not touch or delete that branch.

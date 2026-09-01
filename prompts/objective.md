# Objective

Build **Portfolio Intel**, an agentic system that supplements (not replaces) the
company's existing AI Intake/approval/governance workflow by answering the
questions leadership can't currently answer from the raw governance data:

- Which AI use cases should be prioritized?
- Which pilots should scale?
- Which initiatives are duplicative / could be reused instead of rebuilt?
- Which use cases are not realizing their expected value?
- Where should investment be increased, reduced, consolidated, or discontinued?

The deliverable is a **working prototype** (Python package, no server, no frontend —
a teammate builds the UI against it), an **executive recommendation output**
(Markdown report generator), and a **demo of several scenarios** run end-to-end,
satisfying the hackathon's stated evaluation axes: prioritization quality, value
realization, reuse identification, and recommendation explainability — every
recommendation the system produces must be traceable to concrete rows/fields in the
source data, not asserted by the LLM on its own authority.

This is explicitly a **decision-support / intelligence layer**, not a replacement
for the existing intake/governance/approval workflow, and not real financial or
investment execution.

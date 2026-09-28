# Agent package

`agent.py` derives lake capabilities from OpenAPI, runs reads, records proposals, follows delegated
tasks and enforces the current turn's methodology and solution registries. `evals.py` generates
live capability cases and adds registry-graded methodology and solution questions plus a measured
solution readout. `service.py` exposes the turn API, while `lake_bus.py` receives delegated turns
from lake.

Prompt text lives in [`prompts/`](prompts/). Registry behavior is documented in
[`../../docs/methodologies/`](../../docs/methodologies/) and
[`../../docs/solutions/`](../../docs/solutions/).

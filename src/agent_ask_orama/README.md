# Agent package

`agent.py` derives lake capabilities from OpenAPI, runs reads, records proposals, follows delegated
tasks and enforces the current turn's methodology registry. `evals.py` generates live capability
cases and adds registry-graded M-3 segmentation and M-14 speech questions. `service.py` exposes the
turn API, while `lake_bus.py` receives delegated turns from lake.

Prompt text lives in [`prompts/`](prompts/). Methodology behavior is documented in
[`../../docs/methodologies/`](../../docs/methodologies/).

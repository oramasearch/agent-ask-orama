# Agent package

`agent.py` derives lake capabilities from OpenAPI, runs reads, records proposals, follows delegated
tasks, sends ApplicationAgent work as `app` turns, routes ExperimentsAgent work by experiment kind,
blocks experiment confirmation objects, and enforces the current turn's methodology and solution
registries. `evals.py` generates live capability cases and adds fixed App/build and experiment
cases, registry-graded methodology and solution questions, and a measured solution readout.
`service.py` exposes the turn API, while `lake_bus.py` receives delegated turns from lake.

Prompt text lives in [`prompts/`](prompts/). Domain behavior is documented in
[`../../docs/apps/`](../../docs/apps/), [`../../docs/methodologies/`](../../docs/methodologies/) and
[`../../docs/solutions/`](../../docs/solutions/). ExperimentsAgent routing is documented in
[`../../docs/experiments/`](../../docs/experiments/).

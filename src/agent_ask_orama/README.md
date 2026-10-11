# Agent package

`agent.py` derives lake capabilities from OpenAPI, runs reads, records proposals, follows delegated
tasks, sends ApplicationAgent work as `app` turns, routes ExperimentsAgent work by experiment kind,
blocks experiment confirmation objects, enforces the current turn's methodology and solution
registries, compares trained models by held-out score (`compare_models`), and ends a turn that ran
out of tool rounds with an honest partial answer marked `incomplete`. `evals.py` generates live capability cases and adds fixed App/build and experiment
cases, registry-graded methodology and solution questions, a measured solution readout, and a model-score case.
`service.py` exposes the turn API, while `lake_bus.py` receives delegated turns from lake.

Prompt text lives in [`prompts/`](prompts/). Domain behavior is documented in
[`../../docs/apps/`](../../docs/apps/), [`../../docs/methodologies/`](../../docs/methodologies/) and
[`../../docs/solutions/`](../../docs/solutions/), and model comparison in
[`../../docs/models/`](../../docs/models/). ExperimentsAgent routing is documented in
[`../../docs/experiments/`](../../docs/experiments/).

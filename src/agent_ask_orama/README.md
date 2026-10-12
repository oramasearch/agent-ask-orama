# Agent package

`agent.py` derives lake capabilities from OpenAPI (every workspace engine capability by its own
name, an older lake's through `workspace_query` / `workspace_act`, less the named ceremonies in
`EXCLUDED_CAPABILITIES`; [`../../docs/capabilities/`](../../docs/capabilities/)), runs reads, records proposals, follows delegated
tasks, sends ApplicationAgent work as `app` turns, routes ExperimentsAgent work by experiment kind,
blocks experiment confirmation objects, lists the workspace's connected MCP tools and reads them as data or proposes their changes (`mcp_tool`, lake#652), enforces the current turn's methodology and solution
registries, tells the model whether a turn's page is Design → Agents or Train → Agents
(`agent_page_work`, lake#653; [`../../docs/agents/`](../../docs/agents/)), compares trained models by held-out score (`compare_models`), and ends a turn that ran
out of tool rounds with an honest partial answer marked `incomplete`. `evals.py` generates live capability cases and adds fixed App/build and experiment
cases, registry-graded methodology and solution questions, a measured solution readout, a model-score case, and a workspace-entities case (an experiment,
a search index and an agent), and agent-place and agent-page cases (`run_case` sends each case from its page).
`service.py` exposes the turn API, while `lake_bus.py` receives delegated turns from lake.

Prompt text lives in [`prompts/`](prompts/). Domain behavior is documented in
[`../../docs/apps/`](../../docs/apps/), [`../../docs/methodologies/`](../../docs/methodologies/) and
[`../../docs/solutions/`](../../docs/solutions/), and model comparison in
[`../../docs/models/`](../../docs/models/). ExperimentsAgent routing is documented in
[`../../docs/experiments/`](../../docs/experiments/), and connected MCP tools in
[`../../docs/mcp/`](../../docs/mcp/).

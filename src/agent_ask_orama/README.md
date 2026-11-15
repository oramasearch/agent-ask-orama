# Agent package

`agent.py` derives lake capabilities from OpenAPI (every workspace engine capability by its own
name, an older lake's through `workspace_query` / `workspace_act`, less the named ceremonies in
`EXCLUDED_CAPABILITIES`; [`../../docs/capabilities/`](../../docs/capabilities/)), runs reads, records proposals, follows delegated
tasks, sends Application Agent work as `app` turns, routes Experiments Agent work by experiment kind,
blocks experiment confirmation objects, lists the workspace's connected MCP tools and reads them as data or proposes their changes (`mcp_tool`, lake#652), enforces the current turn's methodology and solution
registries, tells the model whether a turn's page is Design → Agents or Train → Agents
(`agent_page_work`, lake#653; [`../../docs/agents/`](../../docs/agents/)), compares trained models by held-out score (`compare_models`), trims a long read by its items with each list's exact count (`fit`, [`../../docs/reads/`](../../docs/reads/)), checks that a proposal's project exists before recording it and reads Lake's record of earlier proposals (`project_refusal`, `proposal_states`, `points_at_nothing`; [`../../docs/proposals/`](../../docs/proposals/)), and ends a turn that ran
out of tool rounds with an honest partial answer marked `incomplete`. `evals.py` generates live capability cases and adds fixed App/build and experiment
cases, registry-graded methodology and solution questions, a measured solution readout, a model-score case, count cases graded by the exact number, and a workspace-entities case (an experiment,
a search index and an agent), and agent-place and agent-page cases (`run_case` sends each case from its page).
`methodology_draft.py` answers lake's `methodology_draft` turns (lake#688): the three files of a
workspace methodology, the lock's hashes looked up in the package index, checked before they are
offered. `service.py` exposes the turn API and routes that turn kind there, while `lake_bus.py` receives delegated turns from lake, claiming each by reference (lake#871: the turn calls Lake with the bus credential and `X-Lake-Agent-Task`, and falls back to the body's credential on a Lake that refuses it).
`conversations.py` is the service's conversation memory, bounded by count, turns, bytes and idle
time (agent-ask-orama#44).

Prompt text lives in [`prompts/`](prompts/). Domain behavior is documented in
[`../../docs/apps/`](../../docs/apps/), [`../../docs/methodologies/`](../../docs/methodologies/) and
[`../../docs/solutions/`](../../docs/solutions/), and model comparison in
[`../../docs/models/`](../../docs/models/). Experiments Agent routing is documented in
[`../../docs/experiments/`](../../docs/experiments/), and connected MCP tools in
[`../../docs/mcp/`](../../docs/mcp/).

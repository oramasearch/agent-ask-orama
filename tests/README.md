# Tests

`test_agent.py` uses an `httpx` fake lake and a scripted model client. Its methodology coverage
includes a runnable M-3 proposal, an M-14 proposal declined with `zetta#1053`, the M-1-only fallback
for an older engine, and deterministic grading of the segmentation and speech eval cases. Its
solution coverage includes a runnable entry, a preview with missing production components, a
refused sketch, an older engine, policy and evidence reads, an unavailable operation, a policy
proposal that is never sent, and deterministic solution eval grading. Its App coverage includes
lists, current health with retained events, build-failure diagnosis, Application Agent delegation
with kind `app`, proposal-only actions and deterministic App eval grading.
Its experiment coverage routes train, tune and best-model requests to `experiment`, progress to
`experiment_status`, and divergence questions to `experiment_explain`; it also proves Ask Orama
cannot forward confirmed proposal or promotion objects and grades the fixed experiment evals.

Its model coverage (agent-ask-orama#14) answers "which model scored best" with one
`compare_models` read ranked by held-out AUC, names an empty project and a failed read, ends a turn
out of tool rounds as incomplete with an honest partial answer (and as `ok: false` from the
service), and grades the model-score eval.

Its capability coverage (agent-ask-orama#16) serves a current lake's OpenAPI, with every engine
capability by its own name: `issue_assignees` is in the index and every excluded ceremony is not;
named reads go by their own name; a named `compile_intent` and `compose_solution` still need this
turn's registries; an older lake's named calls go through `workspace_query` / `workspace_act` by
the engine's name; `compare_models` reads the named `list_models`; prompt v11 keeps no hand-kept
engine call; and the workspace-entities eval needs an experiment, an index and an agent read.

Its read coverage (agent-ask-orama#21) reads a fake `list_datasets` of 63 datasets with full
schemas, longer than one observation, and checks the model sees whole JSON with the exact count;
a list too long even compact keeps as many items as fit and says how many; a paged answer gives
the capability's total and the next cursor; a value with no list is cut with a note; and the count
evals pass only the exact number, read first from the lake, with no hedge.

Its agent coverage (agent-ask-orama#19) checks that prompt v12 names Design → Agents, the Agent
Factory and Train → Agents and drops "Train (agents, data, runs)"; that `/design/agents`,
`/design/agents/new` and `/design/agent` (with or without `/w/<id>`) are design pages and
`/train/agents` and `/train/agent` training pages, and that a turn from one tells the model so;
and grades the `agent_place` and `agent_page` evals, running the page cases through `run_case`
offline (the fake lake as transport, a scripted model).

Its eval and corpus coverage (agent-ask-orama#28) checks that prompt v13 and the `delegate` tool
offer `agent-eval-generator`, `agent-autosuggest-corpus` and `agent-project-corpus` under lake#763's
names, with the eval and training-corpus routing rule, and that the prompt keeps none of the old
names (ApplicationAgent, ExperimentsAgent, Corpus Generator).

`test_lake_bus.py` covers task receipt and result publication on lake's agent bus, and publishes an
unfinished turn as `failed` with its partial answer.

Run all tests with `uv run pytest`.

`test_methodology_draft.py` covers the `methodology_draft` turn (lake#688) with a scripted model
and a fake package index: the three files with `interface`, `entrypoint` and `packages` set by the
agent and an empty lock for the standard library; every wheel's hash from the index for a pinned
package (`pypi_wheel_hashes` against an `httpx` MockTransport, a missing version named); the
manifest checks as Lake reads them; one repair round with the failing findings, then `ok: false`
with them; and the service routing the turn kind and tracing it without the key.

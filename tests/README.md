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

`test_lake_bus.py` covers task receipt and result publication on lake's agent bus, hands the turn
the claim reply's task, account and workspace as `claim`, and publishes an unfinished turn as
`failed` with its partial answer.

`test_by_reference.py` (lake#871) claims by reference: the claim asks `credentials: by_reference`,
the turn gets the bus credential and `X-Lake-Agent-Task`, every Lake read and model call of the turn
sends both, and no bus call sends the header. Against a Lake from before lake#871, which refuses the
field, the claim is asked again without it and the body's own credential is used with no task
header; any other refusal is not retried.

`test_conversation_owner.py` (agent-ask-orama#42) runs bus turns that share one `conversation_id`:
the owner's next turn, with Lake's `prior_turn`, continues the conversation; another account, even
naming the owner's task as its prior turn, and a member of the same workspace with another `kind`
each see a new conversation and leave nothing in the owner's; a direct turn with no claim keeps no
conversation, whatever its body says; and the claim is the claim reply's, not the body's.

Its proposal coverage (lake#1193, lake#1194) serves a lake whose engine holds a set of projects
(`ProjectsLake`): a `compile_intent` for a missing project is refused in the turn and the
`compile_pipeline` with `create_project` that follows is the only proposal; a taken name is
refused; an unreadable project is left to lake; Lake's `context.proposals` is read and its note
reaches the model; a reply pointing at a failed proposal is corrected once; and the service runs the
whole conversation: propose, confirm fails, "create it then", a new valid proposal. See
[`../docs/proposals/`](../docs/proposals/).

`test_bus_backpressure.py` (agent-ask-orama#43, LSR-075) blocks every worker against a fake lake
whose receive answers only unclaimed tasks, and offers more tasks than there are workers: no more
tasks are claimed than there are workers, the rest stay unclaimed and another replica can take one
(this replica then never runs it), a second tenant gets a worker beside the first tenant's burst,
one tenant alone leaves a worker free, nothing is received while every worker is busy, a turn that
raises gives its worker back, and the worker counts come from `AGENT_BUS_WORKERS` and
`AGENT_BUS_TENANT_WORKERS`.

`test_release.py` reads the version from `pyproject.toml` (and the installed package) and checks
that `docs/releases/v<version>.md` exists, names it in its heading and is listed in
`docs/releases/README.md`, and that `/healthz` reports it.

`test_service_auth.py` (agent-ask-orama#37) starts `serve()`'s own handler on a free port: the
right bearer runs the turn; a missing, empty, truncated, extended or scheme-less bearer is `401`
without running it; an unset `AGENT_SERVICE_TOKEN` refuses every turn with `503`; the comparison
goes through `hmac.compare_digest`; and a non-ASCII bearer is refused, not an error.

`test_conversations.py` (agent-ask-orama#44, LSR-076) covers the bounded conversation memory: the
oldest whole turns go first and the system message stays, a conversation is cut to its byte budget
without parting a tool call from its answer, a single turn over budget leaves only the system
message, the least recently used conversation goes past the count and past the total bytes, growth
after a conversation was handed out is counted, an idle conversation expires, `setdefault` and
moving a conversation to a new key work as on a dict, and the limits come from the environment.
Through the service: 40 conversations keep 5 with the limit at 5, a long conversation keeps its
last 3 turns, a turn that fails leaves nothing in the conversation, and a turn writes no file and
logs its trace id without what was said.

Run all tests with `uv run pytest`.

`test_methodology_draft.py` covers the `methodology_draft` turn (lake#688) with a scripted model
and a fake package index: the three files with `interface`, `entrypoint` and `packages` set by the
agent and an empty lock for the standard library; every wheel's hash from the index for a pinned
package (`pypi_wheel_hashes` against an `httpx` MockTransport, a missing version named); the
manifest checks as Lake reads them; one repair round with the failing findings, then `ok: false`
with them; and the service routing the turn kind, writing nothing to disk and logging its trace id
without the key or what was asked.

`test_turn_destinations.py` (agent-ask-orama#39) checks that a turn's credential goes only to Lake
at the service's own `LAKE_URL`: a turn's `lake_url` (another host, scheme or port) is ignored and
every Lake read and the model client use `LAKE_URL`; with `LAKE_URL` unset, blank or not an absolute
http(s) URL without user info, a turn and a methodology draft are refused before any request.

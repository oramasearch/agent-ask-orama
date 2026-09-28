# agent-ask-orama

**Ask Orama**, the general agent for all of lake ([lake#228](https://github.com/oramasearch/lake/issues/228),
[zetta#1018](https://github.com/oramasearch/zetta/issues/1018)), and the first entry of lake's
**Agent Library**. lake shows it as a panel on every page ([lake#236](https://github.com/oramasearch/lake/issues/236))
and calls this service for every message.

## What it does

- **Works as the person, never more.** Each turn carries the key lake delegates from the person's
  session (`lake_token`); lake's policy decides what it may read.
- **Reads** any lake capability the person may read (`lake_read`), including their workspace's
  Zetta through `workspace_query`.
- **Proposes, never writes** (`lake_propose`): a change comes back as a proposal with its impact;
  lake shows it and runs it only when the person confirms.
- **Delegates to any agent** (`delegate`), through lake's `agent_turn`: the Project Agent
  (`agent-project`) for Pipelines, ApplicationAgent (`agent-application`, kind `app`) for Apps,
  ExperimentsAgent (`agent-experiments`) for training studies, Auto-Suggest (`agent-autosuggest`)
  for Opportunities, and every agent the person built. An unattended agent is started by proposing
  `launch_agent`. A library agent answers on lake's agent bus: `agent_turn` returns a task, and Ask
  Orama follows it with `receive_agent_events` for up to four minutes (lake#269). A subagent still
  working then is reported as working, with its task.
- **Its vocabulary is derived.** The capabilities it may name come from lake's `/v1/openapi.json`
  at every turn, less the ceremonies a person performs (signing in, recovering, minting keys).
- **It knows Apps and builds.** It reads App desired and observed state plus retained App events,
  and reads build rows plus retained build events to explain failures. Building or changing an App
  goes to ApplicationAgent. Deploys, rebuilds, rollbacks, scaling and every other App action remain
  proposals until the person confirms them.
- **It delegates training experiments.** Train, tune and best-model requests go to ExperimentsAgent
  as `experiment` turns; progress uses `experiment_status`; results and divergence explanations use
  `experiment_explain`. Ask Orama summarizes the returned proposal or result. It cannot forward a
  confirmed proposal or promotion; lake does that only after the person reviews and confirms it.
- **It knows the current solution catalogue.** On every solution turn it reads `list_solutions`,
  uses `get_solution` for the selected entry, reports missing production foundations and sketches
  honestly, and reads a solution Project's policy, holdout, ledger, monitor and measured readout.
  Policy and solution changes are proposals the person confirms; Ask Orama never applies them.
- **It knows what the engine can run.** For methodology support, Pipeline changes and Pipelines
  that train nothing, it reads the workspace's live `list_methodologies` registry. It proposes
  `compile_intent` or another methodology-bearing edit only when that turn's registry marks the
  methodology runnable; otherwise it names the methodology's Zetta issue. An older workspace
  without the registry is treated as supporting only M-1 churn / GBDT classification.

## Service

`agent-ask-orama-serve` on `PORT` (8080):

| Route | What it does |
|---|---|
| `GET /healthz` | the model and prompt version |
| `POST /v1/turn` | `{conversation_id, message, lake_token, customer_id, page, lake_url?}` → `{ok, conversation_id, trace_id, reply, reads, proposals, delegations, rounds}` |

`AGENT_SERVICE_TOKEN`, when set, is required as a bearer (only lake calls it). `LAKE_URL` is lake's
in-cluster address; `ASK_ORAMA_MODEL` the model (default `gpt-5.5`); `OPENAI_API_KEY` the general
Orama key the operator mounts. Conversations live in memory by id. Every turn is a trace in
`TRACE_DIR`, never with the person's key.

**Turns arrive on lake's agent bus** (lake `docs/api/agent-bus.md`). `lake_bus.py` long-polls
`receive_agent_tasks` through lake with this agent's own bus credential (`AGENT_BUS_TOKEN`). It
claims each task, whose body carries the task's credential as `lake_token`, runs it as
`/v1/turn` would, and publishes `progress`, then the answer or `failed`. It starts when the
operator sets `LAKE_URL`, `AGENT_BUS_TOKEN` and `AGENT_BUS_AGENT`.

## Evals

`ask-orama-evals` (`evals.py`) generates cases from the live lake's capability index (a sample of
changes and reads, requests missing an input, plus delegations) and grades each by rule: a change
must be **proposed** with **no write sent**, a read must be called, a request that needs an id it
does not give must be answered with a question or a lookup first (never a guessed value), a Pipeline
request must reach `agent-project`, an opportunity request `agent-autosuggest`, an App request
`agent-application` with kind `app`, and a training experiment request `agent-experiments` with the
matching turn kind; nothing may name a capability lake does not have. Fixed App cases require the
App list, current state with events, and the last build with build events. Fixed experiment cases
cover train, tune, best-model, progress and divergence requests. Fixed methodology cases ask
whether customer segmentation and speech analytics run; they are graded against the live registry,
including the tracking issue when support is absent. Fixed solution cases grade S-1 and B-1
against the live catalogue, and a measured-readout case requires `get_roi_readout` after
`list_solutions`. Change and read cases sample only capabilities whose required inputs are the
space alone, so they can be done as asked.

```sh
LAKE_URL=https://lake.oramadev.net LAKE_TOKEN=<a person's token> CUSTOMER_ID=<their space> \
  uv run ask-orama-evals --out reports/
```

Reports land in [`reports/`](reports/). No score is claimed here that the runner did not produce.

## Image

Private on Docker Hub as `oramasearch/agent-ask-orama`, built on the cluster BuildKit:

```sh
buildctl --addr "kube-pod://<buildkit pod>?context=orama-production-cluster-01&namespace=buildkit" build \
  --frontend dockerfile.v0 --local context=. --local dockerfile=. --opt platform=linux/amd64 \
  --output type=image,name=docker.io/oramasearch/agent-ask-orama:<tag>,push=true
```

## Tests

`uv run pytest`: the index without ceremonies, reads as the person in their space, a change that is
proposed and never sent, methodology registry enforcement and the old-engine fallback, delegation
through lake, App and build reads with retained events, ApplicationAgent app turns, proposal-only
App actions, ExperimentsAgent routing and confirmation isolation, solution catalogue and
policy/readout behavior, solution and policy proposals that are never sent, unknown capabilities
as observations, the service's conversation and a trace without the key, and the eval grader.

## Documentation

- [`docs/apps/`](docs/apps/) — App and build reads, event-stream diagnosis, ApplicationAgent
  delegation and proposal-only actions.
- [`docs/experiments/`](docs/experiments/) — ExperimentsAgent turn routing, proposal/result
  summaries and the confirmation boundary.
- [`docs/methodologies/`](docs/methodologies/) — registry reads, proposal enforcement, graph
  explanations and old-engine behavior.
- [`docs/solutions/`](docs/solutions/) — catalogue reads, preview and sketch behavior, policy and
  evidence reads, proposal enforcement and old-engine behavior.

## Known failures and limits

- Conversations are in memory: restarting the service forgets them.
- A delegated agent's answer is reported as it came back; Ask Orama does not re-check it.

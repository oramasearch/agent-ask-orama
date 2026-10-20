# agent-ask-orama

**Ask Orama**, the general agent for all of lake ([lake#228](https://github.com/oramasearch/lake/issues/228),
[zetta#1018](https://github.com/oramasearch/zetta/issues/1018)), and the first entry of lake's
**Agent Library**. lake shows it as a panel on every page ([lake#236](https://github.com/oramasearch/lake/issues/236))
and calls this service for every message.

**Current release: [v0.1.1](docs/releases/v0.1.1.md)** (2026-10-19, prompt v14).

## What it does

- **Works as the person, never more.** Each turn carries the key lake delegates from the person's
  session (`lake_token`); lake's policy decides what it may read.
- **Reads** any lake capability the person may read (`lake_read`), including every capability of
  their workspace's engine by its own name (lake#650; through `workspace_query` on an older lake).
- **Proposes, never writes** (`lake_propose`): a change comes back as a proposal with its impact;
  lake shows it and runs it only when the person confirms.
- **Delegates to any agent** (`delegate`), through lake's `agent_turn`, under lake#763's names:
  - the Project Agent (`agent-project`) for Pipelines;
  - the Application Agent (`agent-application`, kind `app`) for Apps;
  - the Experiments Agent (`agent-experiments`) for training studies;
  - the Auto-Suggest Agent (`agent-autosuggest`) for Opportunities;
  - the Eval Generator Agent (`agent-eval-generator`) to create an eval, realistic test cases to
    evaluate an agent;
  - the Auto-Suggest Corpus Agent (`agent-autosuggest-corpus`) for a training corpus of
    what-is-worth-building examples;
  - the Project Corpus Agent (`agent-project-corpus`) for a training corpus of pipeline-building
    examples on the person's workspace;
  - and every agent the person built.

  An eval request goes to the Eval Generator Agent and a training-corpus request to the matching
  corpus agent; when the person does not say which agent the corpus trains, Ask Orama asks
  (prompt v13, [agent-ask-orama#28](https://github.com/oramasearch/agent-ask-orama/issues/28)).
  The Agent Factory, where the Agent Creator Agent drafts a new agent, is a page in Design →
  Agents, not a delegation. An unattended agent is started by proposing
  `launch_agent`. A library agent answers on lake's agent bus: `agent_turn` returns a task, and Ask
  Orama follows it with `receive_agent_events` for up to four minutes (lake#269). A subagent still
  working then is reported as working, with its task.
- **How-to answers come from Lake's Docs.** A question about using Lake is answered from the
  guide `list_docs` and `get_doc` find, naming each page as the navigation shows it, linked, and
  only the formats it states (prompt v14, [lake#817](https://github.com/oramasearch/lake/issues/817),
  [`docs/how-to/`](docs/how-to/README.md)).
- **Its vocabulary is derived.** The capabilities it may name come from lake's `/v1/openapi.json`
  at every turn, less the ceremonies a person performs (signing in, recovering, minting
  credentials, reading secrets in the clear), named one by one in `EXCLUDED_CAPABILITIES`
  ([`docs/capabilities/`](docs/capabilities/), agent-ask-orama#16).
- **It knows Apps and builds.** It reads App desired and observed state plus retained App events,
  and reads build rows plus retained build events to explain failures. Building or changing an App
  goes to Application Agent. Deploys, rebuilds, rollbacks, scaling and every other App action remain
  proposals until the person confirms them.
- **It delegates training experiments.** Train, tune and best-model requests go to Experiments Agent
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

- **It writes the first draft of a workspace methodology** (lake#688). Lake's New Methodology
  drawer sends a `methodology_draft` turn; Ask Orama answers `methodology.json`, `methodology.py`
  and a `requirements.lock` whose every pin carries the hashes of its wheels from the package index,
  checked the way Lake's Validate checks code before anything runs. Nothing is written: the person
  reviews it and Create commits it ([`docs/methodologies/`](docs/methodologies/#drafting-a-workspace-methodology-lake688)).

- **It compares trained models in one read.** `compare_models` lists every model (or one
  project's) with its held-out scores, best first, from the workspace's `list_models`, so "which
  model scored best" is answered within the turn (agent-ask-orama#14, [`docs/models/`](docs/models/)).
- **A long list is counted, never cut silently.** A read longer than one observation is trimmed
  by its items, not sliced mid-text, and carries each list's count taken before trimming (or the
  capability's own `total`) and how many items it shows; a paged answer says more follow
  (agent-ask-orama#21, [`docs/reads/`](docs/reads/)).
- **An unfinished turn is never a success.** When the tool rounds run out, Ask Orama says it did
  not finish, what it found and what is still unknown; the turn answers `ok: false` with
  `incomplete: true`, and lake's agent bus records it as `failed`.

## Service

`agent-ask-orama-serve` on `PORT` (8080):

| Route | What it does |
|---|---|
| `GET /healthz` | the agent, its release `version`, the model and prompt version |
| `POST /v1/turn` | `{conversation_id, message, lake_token, customer_id, page, lake_url?}` → `{ok, conversation_id, trace_id, reply, reads, proposals, delegations, rounds, incomplete}`; a turn out of tool rounds is `ok: false` (HTTP 422) with its partial answer as `error` |

`AGENT_SERVICE_TOKEN`, when set, is required as a bearer (only lake calls it). `LAKE_URL` is lake's
in-cluster address; `ASK_ORAMA_MODEL` the model (default `gpt-5.5`). **The model is reached through
lake** (lake#248, lake `docs/api/model-gateway.md`): every call goes to `<lake_url>/openai/v1` with the
turn's own `lake_token` as the API key (`model.py`), so lake counts its tokens in the turn's workspace
and enforces the account's model-token limit. The service needs no `OPENAI_API_KEY`; only the offline
evals (`evals.py`), which run for no workspace, call OpenAI directly. Conversations live in memory by
id. Every turn is a trace in
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
`agent-application` with kind `app`, an eval request `agent-eval-generator`, a training-corpus
request `agent-autosuggest-corpus` or `agent-project-corpus` (agent-ask-orama#28), and a training
experiment request `agent-experiments` with the matching turn kind; nothing may name a capability lake does not have. Fixed App cases require the
App list, current state with events, and the last build with build events. Fixed experiment cases
cover train, tune, best-model, progress and divergence requests. Fixed methodology cases ask
whether customer segmentation and speech analytics run; they are graded against the live registry,
including the tracking issue when support is absent. Fixed solution cases grade S-1 and B-1
against the live catalogue, and a measured-readout case requires `get_roi_readout` after
`list_solutions`. A model-score case asks which trained model scored best and requires `list_models`
and a held-out figure in the reply. Count cases ask how many datasets, trained models and runs the
workspace has and grade the exact number the runner read first, failing a hedge such as "at
least" or "cut off" (agent-ask-orama#21). Fixed agent cases (agent-ask-orama#19) require a new agent to be
sent to Design → Agents or the Agent Factory and improving one to Train → Agents, and a turn asked
from `/design/agents`, `/design/agent` or `/train/agent` to speak of designing or training the
agent; every case fails when its turn ran out of tool rounds. Change and read cases sample only capabilities whose required inputs are the
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
through lake, the eval and corpus agents and lake#763's agent names in the prompt and the
`delegate` tool, App and build reads with retained events, Application Agent app turns, proposal-only
App actions, Experiments Agent routing and confirmation isolation, solution catalogue and
policy/readout behavior, solution and policy proposals that are never sent, unknown capabilities
as observations, `compare_models` ranking held-out scores, a long list trimmed by its items with
its exact count and a paged answer's total and cursor, Design → Agents and Train → Agents in the prompt and a
turn's agent page, the agent-place and agent-page evals run offline, a turn out of tool rounds ending
unfinished (and published as `failed`), the service's conversation and a trace without the key,
the eval grader, and the `methodology_draft` turn (three files, lock hashes from the index, the
manifest and entrypoint checks, one repair round, a failing draft answered with its findings, and
its trace without the key).

## Documentation

- [`docs/releases/`](docs/releases/) — one page per release: what it includes, what it does not,
  known issues and verification.
- [`docs/agents/`](docs/agents/) — Design → Agents and the Agent Factory for designing an agent,
  Train → Agents for training one (lake#653), the agent pages a turn is asked from, and evals and
  training corpora handed to the Eval Generator, Auto-Suggest Corpus and Project Corpus Agents.
- [`docs/reads/`](docs/reads/) — what one read hands the model: a long list trimmed by its items
  with its exact count, paged answers, and the said cut of last resort.
- [`docs/apps/`](docs/apps/) — App and build reads, event-stream diagnosis, Application Agent
  delegation and proposal-only actions.
- [`docs/experiments/`](docs/experiments/) — Experiments Agent turn routing, proposal/result
  summaries and the confirmation boundary.
- [`docs/models/`](docs/models/) — comparing trained models by held-out score
  (`compare_models`), and how a turn out of tool rounds ends as failed with a partial answer.
- [`docs/methodologies/`](docs/methodologies/) — registry reads, proposal enforcement, graph
  explanations, old-engine behavior, and drafting a workspace methodology (lake#688).
- [`docs/solutions/`](docs/solutions/) — catalogue reads, preview and sketch behavior, policy and
  evidence reads, proposal enforcement and old-engine behavior.

## Known failures and limits

- Conversations are in memory: restarting the service forgets them.
- A delegated agent's answer is reported as it came back; Ask Orama does not re-check it.

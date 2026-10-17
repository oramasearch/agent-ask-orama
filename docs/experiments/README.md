# Training experiments

Ask Orama delegates training-study work to Experiments Agent, library key `agent-experiments`.
Experiments Agent owns study design, live monitoring and result analysis; Ask Orama carries the
request through lake's agent bus and summarizes the returned proposal or result in the conversation.

## Turn routing

| Person's request | Turn kind | Ask Orama's response |
|---|---|---|
| Train a model, tune one, or find the best model | `experiment` | Summarize the proposed objective, search space, sampler, pruner and budgets; say it awaits review. |
| Show study or trial progress, budget or live metrics | `experiment_status` | Summarize returned study, trial, budget and metric facts. |
| Explain results, the best trial, parameter importance, next search, caveats or divergence | `experiment_explain` | Summarize the returned result and its evidence without inventing a cause or metric. |

The delegate request includes known dataset, Project, Pipeline, methodology, objective, study and
run identifiers, plus relevant page context. When a status or explanation request has no study or
run identifier in the conversation or page, Ask Orama asks for it instead of guessing.

## Confirmation contract

An initial `experiment` turn is read-only. Experiments Agent returns a proposal with confirmation
required and does not create a study. Ask Orama reports that proposal as proposed, never running,
and directs the person to review and confirm it in lake.

Ask Orama refuses `context.confirmed_proposal` and `context.confirmed_promotion`. Plain-text
approval in the conversation is not confirmation. After the person confirms in lake, lake supplies
the reviewed object to Experiments Agent on its confirmed turn. The same rule protects trial
promotion. Ask Orama never calls `start_study` or `promote_trial` in place of delegation.

## Registered lake calls

Delegation uses only lake's registered REST/MCP capabilities:

- `agent_turn` creates the Experiments Agent task with one of the three turn kinds.
- `receive_agent_events` follows that task and returns its proposal, status or explanation.

Experiments Agent performs its own experiment reads through lake. The initial design turn may use
free reads, but study creation and trial promotion remain behind lake's confirmation fields.

The fake-lake tests cover all three turn kinds, each issue phrase (`train`, `tune`, `find the best
model`, and divergence), proposal/result summaries, registered calls, and rejection of confirmation
objects. Generated evals add the same fixed routes to the live capability-derived cases.

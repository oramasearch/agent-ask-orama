# Designing and Training Agents

Where Ask Orama sends a person for agent work, and how it answers from Lake Console's agent pages
([agent-ask-orama#19](https://github.com/oramasearch/agent-ask-orama/issues/19), after
[lake#653](https://github.com/oramasearch/lake/issues/653)).

## Two Homes for Agents

lake#653 split agent work across two pages of Lake Console:

| Page | Path | What it is for |
|---|---|---|
| Design → Agents | `/design/agents`, `/design/agent?id=…`, `/design/agents/new` (the Agent Factory) | designing an agent: a new agent (purpose, prompt, skills, model, pipelines, schedule), Orama's agents to duplicate, an agent's definition, revisions and edits. Was *Agent Library*; `/design/agent-library` and `/train/agents/new` redirect here |
| Train → Agents | `/train/agents`, `/train/agent?id=…` | training and improving the agents that learn: performance over time, trained versions and their data, promote and roll back, experiments |

Before prompt `v12`, Ask Orama described the product as "Train (agents, data, runs)" and so sent
people to Train to build an agent. Prompt `v12`:

- names Design as projects, Pipelines, solutions and agents, and Train as agents to train, runs,
  experiments and models;
- sends a person who wants a **new agent** (or to change what an agent is) to **Design → Agents**
  or the **Agent Factory**, never to Train;
- sends a person who wants an agent to **get better** (a higher score, new data, promote or roll
  back a version, an experiment) to **Train → Agents**, and says that an agent with nothing to
  train is not listed there.

## The Page a Turn Is Asked From

A turn carries the page the person is on (`page`, with its `path` and query values, lake#258).
`agent_page_work` in `agent.py` reads that path, with or without the workspace's `/w/<id>` prefix:

- `/design/agents`, `/design/agents/new`, `/design/agent` → `design`;
- `/train/agents`, `/train/agent` → `train`;
- anything else (including the old `/design/agent-library`) → nothing.

`page_text` appends the page to the person's message as before and, on an agent page, says which
work it is: `Design → Agents, where an agent is designed. Speak of designing it` or
`Train → Agents, where an agent that learns is trained. Speak of training it`. The prompt says the
same, and that the page's `id` is the agent to read before saying anything about it.

## Evals

`evals.py` adds five fixed cases, graded by rule:

| Case | Kind | Asked from | Passes when the reply |
|---|---|---|---|
| `agent-new` | `agent_place` | — | names Design → Agents or the Agent Factory |
| `agent-improve` | `agent_place` | — | names Train → Agents |
| `page-design-agents` | `agent_page` | `/design/agents` | speaks of designing, not more of training |
| `page-design-agent` | `agent_page` | `/design/agent?id=agent-1` | speaks of designing, not more of training |
| `page-train-agent` | `agent_page` | `/train/agent?id=agent-1` | speaks of training, not more of designing |

Page names are matched however the arrow is written (`→`, `->`, `>`, `›`), and naming the other
page ("train it on Train → Agents") is offering it, not speaking of it, so it is not counted. A
case's `page` is sent with its turn (`run_case`). The runner also counts a POST to any read
capability, and to `list_mcp_connection_tools`, as a read, so the connected-tools listing every
turn sends (lake#652) is not graded as a write.

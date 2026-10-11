"""Ask Orama without a network: lake is an httpx MockTransport, the model a scripted client.
The live eval set (evals/) runs against a real lake."""

from __future__ import annotations

import json
from types import SimpleNamespace

import httpx

from agent_ask_orama import agent, service

CUSTOMER = [{"in": "query", "name": "customer_id", "required": True}]


def body(*names):
    return {"content": {"application/json": {"schema": {
        "properties": {name: {"type": "string"} for name in names}}}}}


OPENAPI = {"paths": {
    "/v1/list_repositories": {"get": {"summary": "List repositories", "parameters": CUSTOMER}},
    "/v1/identity": {"get": {"summary": "This lake's identity", "parameters": []}},
    "/v1/get_repository": {"get": {"summary": "Get a repository", "parameters": CUSTOMER + [
        {"in": "query", "name": "repository_id", "required": True}]}},
    "/v1/list_apps": {"get": {"summary": "List Apps", "parameters": CUSTOMER}},
    "/v1/get_app": {"get": {"summary": "Get an App", "parameters": CUSTOMER + [
        {"in": "query", "name": "app_id", "required": True}]}},
    "/v1/receive_app_events": {"get": {"summary": "Receive App events",
                                          "parameters": CUSTOMER + [
        {"in": "query", "name": "app_id", "required": True}]}},
    "/v1/list_builds": {"get": {"summary": "List builds", "parameters": CUSTOMER}},
    "/v1/get_build": {"get": {"summary": "Get a build", "parameters": CUSTOMER + [
        {"in": "query", "name": "build_id", "required": True}]}},
    "/v1/receive_build_events": {"get": {"summary": "Receive build events",
                                            "parameters": CUSTOMER + [
        {"in": "query", "name": "build_id", "required": True}]}},
    # As lake serves it: a POST (its input is an object) that only reads.
    "/v1/workspace_query": {"post": {"summary": "Query a workspace", "x-lake-action": "read",
                                     "requestBody": body("customer_id", "capability")}},
    "/v1/workspace_act": {"post": {"summary": "Act in a workspace",
                                   "requestBody": body("customer_id", "capability", "input")}},
    "/v1/create_repository": {"post": {"summary": "Create a repository",
                                       "requestBody": body("customer_id", "name")}},
    "/v1/create_app": {"post": {"summary": "Create an App",
                                  "requestBody": body("customer_id", "name")}},
    "/v1/deploy_app": {"post": {"summary": "Deploy an App",
                                  "requestBody": body("customer_id", "app_id")}},
    "/v1/build_app": {"post": {"summary": "Build an App",
                                 "requestBody": body("customer_id", "app_id")}},
    "/v1/rollback_app": {"post": {"summary": "Roll back an App",
                                    "requestBody": body("customer_id", "app_id")}},
    "/v1/scale_app": {"post": {"summary": "Scale an App",
                                 "requestBody": body("customer_id", "app_id", "replicas")}},
    "/v1/agent_turn": {"post": {"summary": "Talk to an agent",
                                "requestBody": body("customer_id", "agent", "kind", "message",
                                                    "context")}},
    "/v1/receive_agent_events": {"get": {"summary": "Receive agent events",
                                              "parameters": CUSTOMER + [
        {"in": "query", "name": "task_id", "required": True}]}},
    "/v1/sign_in_password": {"post": {"summary": "Sign in"}},
    "/v1/repositories/{id}/sync/push": {"post": {"summary": "binary"}},
}}

# Lake requires REST/OpenAPI and MCP tools/list parity. This is the fake tools/list projection.
LAKE_MCP_TOOLS = frozenset(
    path.removeprefix("/v1/")
    for path in OPENAPI["paths"]
    if path.startswith("/v1/") and "{" not in path
)

METHODOLOGIES = [
    {"id": "M-1", "name": "Tabular supervised", "runnable": True, "partial": False,
     "issue": None},
    {"id": "M-3", "name": "Segmentation / clustering", "runnable": True, "partial": False,
     "issue": "zetta#1042"},
    {"id": "M-14", "name": "Speech", "runnable": False, "partial": False,
     "issue": "zetta#1053"},
]

SOLUTIONS = [
    {
        "id": "S-1",
        "name": "Customer retention",
        "promise": "Prioritize retention work from measured customer risk.",
        "use_case": "Retention operations",
        "composition": [
            {"id": "M-1", "role": "risk ranking", "minimum_level": 1},
            {"id": "M-6", "role": "incrementality", "minimum_level": 3},
        ],
        "levels": [
            {"level": 1, "name": "Rank", "description": "Rank customer risk."},
            {"level": 2, "name": "Act", "description": "Route reviewed actions."},
        ],
        "action_patterns": ["reviewed outreach"],
        "latency": ["batch"],
        "autonomy": [{"action_class": "outreach", "autonomy": "approval_required"}],
        "data_roles": [{"role": "customer history", "required": True}],
        "runnable": True,
        "status": "available",
        "missing": [],
        "issue": "zetta#1102",
    },
    {
        "id": "S-2",
        "name": "Expansion signals",
        "promise": "Surface accounts that merit review for expansion.",
        "use_case": "Account expansion",
        "composition": [{"id": "M-3", "role": "cohorts", "minimum_level": 1}],
        "levels": [{"level": 1, "name": "Discover", "description": "Find cohorts."}],
        "action_patterns": ["sales review"],
        "latency": ["batch"],
        "autonomy": [{"action_class": "sales_task", "autonomy": "approval_required"}],
        "data_roles": [{"role": "account activity", "required": True}],
        "runnable": False,
        "status": "preview",
        "missing": [
            {"id": "decision-policy", "name": "decision policy engine", "issue": "zetta#1104"},
            {"id": "measured-readout", "name": "measured-value readout", "issue": "zetta#1108"},
        ],
        "issue": "zetta#1102",
    },
    {
        "id": "B-1",
        "name": "Procurement sketch",
        "promise": "Explore governed procurement actions.",
        "use_case": "Procurement",
        "composition": [],
        "levels": [],
        "action_patterns": [],
        "latency": [],
        "autonomy": [],
        "data_roles": [{"role": "purchase history", "required": True}],
        "runnable": False,
        "status": "sketch",
        "missing": [],
        "promotion_condition": "add supported methodology callbacks",
        "issue": "zetta#1102",
    },
]


# Two finished runs of one project (the second with a larger holdout), one run without a holdout,
# and a model in another project: list_models as the engine answers it.
MODELS = [
    {"id": "m-1", "name": "churn model", "kind": "gbdt", "project": "p-1",
     "project_name": "api_churn", "pipeline_name": "churn", "run": "run one", "run_id": "r-1",
     "created": "2026-10-10T10:00:00Z", "exposed": False, "has_weights": True,
     "metrics": {"held_out_auc": 0.874, "held_out_accuracy": 0.80, "held_out_log_loss": 0.41,
                 "held_out_rows": 300, "auc": 0.97}},
    {"id": "m-2", "name": "churn model", "kind": "gbdt", "project": "p-1",
     "project_name": "api_churn", "pipeline_name": "churn", "run": "run two", "run_id": "r-2",
     "created": "2026-10-10T11:00:00Z", "exposed": False, "has_weights": True,
     "metrics": {"held_out_auc": 0.890, "held_out_accuracy": 0.812, "held_out_log_loss": 0.383,
                 "held_out_rows": 292, "auc": 0.95}},
    {"id": "m-3", "name": "churn model", "kind": "gbdt", "project": "p-1",
     "project_name": "api_churn", "pipeline_name": "churn", "run": "run three", "run_id": "r-3",
     "created": "2026-10-10T12:00:00Z", "exposed": False, "has_weights": True,
     "metrics": {"auc": 0.99, "accuracy": 0.97}},
    {"id": "m-9", "name": "other", "kind": "gbdt", "project": "p-2", "project_name": "elsewhere",
     "pipeline_name": "x", "run": "run nine", "run_id": "r-9", "created": "2026-10-09T09:00:00Z",
     "exposed": True, "has_weights": True, "metrics": {"held_out_auc": 0.99}},
]


class FakeLake:
    def __init__(self, methodology_response=None, solution_response=None,
                 solution_operations=None) -> None:
        self.requests: list[httpx.Request] = []
        self.polls = 0
        self.methodology_response = methodology_response or {
            "ok": True,
            "value": {"methodologies": METHODOLOGIES},
        }
        self.solution_response = solution_response or {
            "ok": True,
            "value": {"solutions": SOLUTIONS},
        }
        self.solution_operations = solution_operations or {
            "get_policy": {"ok": True, "value": {
                "project": "retention", "version": 3,
                "rules": [{"when": "risk is high", "action": "request review"}],
            }},
            "get_experiment": {"ok": True, "value": {
                "project": "retention", "status": "collecting",
            }},
            "list_ledger": {"ok": True, "value": {
                "entries": [{"score": "recorded", "decision": "review",
                             "action": "pending", "outcome": "not_observed"}],
            }},
            "get_monitor": {"ok": True, "value": {
                "project": "retention", "status": "healthy",
            }},
            "get_roi_readout": {"ok": True, "value": {
                "project": "retention", "status": "insufficient_evidence",
                "measured_value": None,
            }},
        }

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.url.path == "/v1/openapi.json":
            return httpx.Response(200, json=OPENAPI)
        if request.url.path == "/v1/list_repositories":
            return httpx.Response(200, json={"ok": True, "value": {"items": [{"name": "site"}]}})
        if request.url.path == "/v1/list_apps":
            return httpx.Response(200, json={"ok": True, "value": {"apps": [{
                "id": "app-1", "name": "risk-console", "desired": "running",
                "status": {"phase": "Running", "ready": True},
            }]}})
        if request.url.path == "/v1/get_app":
            return httpx.Response(200, json={"ok": True, "value": {"app": {
                "id": request.url.params["app_id"], "name": "risk-console",
                "desired": "running", "generation": 4,
                "status": {"phase": "Running", "ready": True,
                           "observed_generation": 4, "message": "healthy"},
            }}})
        if request.url.path == "/v1/receive_app_events":
            return httpx.Response(200, json={"ok": True, "value": {
                "events": [{"sequence": 1, "phase": "Running", "message": "healthy"}],
                "next_sequence": 2,
            }})
        if request.url.path == "/v1/list_builds":
            return httpx.Response(200, json={"ok": True, "value": {"builds": [{
                "id": "build-9", "app_id": "app-1", "phase": "failed",
                "created_at": "2026-09-28T12:00:00Z",
            }]}})
        if request.url.path == "/v1/get_build":
            return httpx.Response(200, json={"ok": True, "value": {"build": {
                "id": request.url.params["build_id"], "app_id": "app-1", "phase": "failed",
                "message": "dependency install failed",
            }}})
        if request.url.path == "/v1/receive_build_events":
            return httpx.Response(200, json={"ok": True, "value": {
                "events": [{"sequence": 1, "type": "error",
                            "message": "package lock is out of date"}],
                "next_sequence": 2,
            }})
        if request.url.path == "/v1/identity":
            if "customer_id" in request.url.params:
                return httpx.Response(400, json={"ok": False, "error": {
                    "code": "invalid_input", "message": "unexpected field customer_id"}})
            return httpx.Response(200, json={"ok": True, "value": {"id": "taap:lake"}})
        if request.url.path == "/v1/workspace_query":
            if request.method != "POST":
                return httpx.Response(405, json={"ok": False, "error": {
                    "code": "method_not_allowed", "message": "call it with POST"}})
            sent = json.loads(request.content)
            if sent.get("capability") == "list_methodologies":
                return httpx.Response(200, json=self.methodology_response)
            if sent.get("capability") == "list_solutions":
                return httpx.Response(200, json=self.solution_response)
            if sent.get("capability") == "get_solution":
                solution_id = (sent.get("input") or {}).get("solution")
                solutions = (self.solution_response.get("value") or {}).get("solutions") or []
                solution = next((item for item in solutions if item.get("id") == solution_id), None)
                if solution is None:
                    return httpx.Response(200, json={"ok": False, "error": {
                        "code": "not_found", "message": f"unknown solution {solution_id}"}})
                return httpx.Response(200, json={"ok": True, "value": {"solution": solution}})
            if sent.get("capability") == "list_models":
                return httpx.Response(200, json={"ok": True, "value": {"models": MODELS}})
            if sent.get("capability") in self.solution_operations:
                return httpx.Response(200, json=self.solution_operations[sent["capability"]])
            return httpx.Response(200, json={"ok": True, "value": {"datasets": [
                {"database": "datasets", "name": "accounts", "rows": 200}]}})
        if request.url.path == "/v1/agent_turn":
            sent = json.loads(request.content)
            if sent["agent"] in {"agent-project", "agent-application", "agent-experiments"}:
                # A library agent: the turn is a task on lake's agent bus (lake#269).
                task_ids = {
                    "app": "t-app",
                    "experiment": "t-experiment",
                    "experiment_status": "t-experiment-status",
                    "experiment_explain": "t-experiment-explain",
                }
                task_id = task_ids.get(sent.get("kind"), "t-1")
                return httpx.Response(200, json={"ok": True, "value": {
                    "task_id": task_id, "agent": sent["agent"], "status": "pending"}})
            return httpx.Response(200, json={"ok": True, "value": {
                "agent": sent["agent"], "reply": "built a churn Pipeline"}})
        if request.url.path == "/v1/receive_agent_events":
            self.polls += 1
            status = "running" if self.polls < 2 else "succeeded"
            task_id = request.url.params["task_id"]
            results = {
                "t-app": ("agent-application", {
                    "reply": "proposed the risk console App",
                }),
                "t-experiment": ("agent-experiments", {
                    "kind": "proposal",
                    "confirm": True,
                    "proposal": {
                        "objective": "minimize validation loss",
                        "search_space": ["learning_rate", "max_depth"],
                        "budgets": {"max_trials": 12},
                    },
                }),
                "t-experiment-status": ("agent-experiments", {
                    "kind": "status",
                    "study": "study-7",
                    "completed_trials": 4,
                    "budget_trials": 12,
                }),
                "t-experiment-explain": ("agent-experiments", {
                    "kind": "explanation",
                    "run": "run-4",
                    "cause": "gradient norm became non-finite",
                }),
            }
            agent_name, result = results.get(task_id, (
                "agent-project",
                {"reply": "built a churn Pipeline"},
            ))
            answer = {"ok": True, "result": result}
            return httpx.Response(200, json={"ok": True, "value": {
                "events": [], "next_sequence": self.polls + 1,
                "task": {"task_id": task_id, "agent": agent_name, "status": status,
                         "answer": answer if status == "succeeded" else None}}})
        return httpx.Response(403, json={"ok": False, "error": {"code": "unauthorized",
                                                                "message": "no"}})


def message(content=None, tool_calls=None):
    value = SimpleNamespace(content=content, tool_calls=tool_calls)
    value.model_dump = lambda exclude_none=True: {"role": "assistant", "content": content or ""}
    return SimpleNamespace(choices=[SimpleNamespace(message=value)])


def call(name, **arguments):
    return SimpleNamespace(id=f"c-{name}", function=SimpleNamespace(
        name=name, arguments=json.dumps(arguments)))


class Scripted:
    def __init__(self, *replies) -> None:
        self.replies = list(replies)
        self.seen: list[list] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.seen.append(list(kwargs["messages"]))
        return self.replies.pop(0)


def turn(**overrides):
    value = {"message": "hi", "lake_url": "http://lake", "lake_token": "person-key",
             "customer_id": "c-1"}
    value.update(overrides)
    return agent.Turn(**value)


def lake_for(fake):
    return lambda t: agent.Lake(t, transport=httpx.MockTransport(fake))


def run(client, fake, history=None, **overrides):
    t = turn(**overrides)
    return agent.answer_turn(t, history if history is not None else [], client, "gpt-5.5",
                             agent.Lake(t, transport=httpx.MockTransport(fake)))


def test_the_index_is_lakes_own_openapi_without_ceremonies():
    index = agent.capability_index(OPENAPI)
    assert set(index) == {
        "list_repositories", "identity", "get_repository", "list_apps", "get_app",
        "receive_app_events", "list_builds", "get_build", "receive_build_events",
        "workspace_query", "workspace_act", "create_repository", "create_app", "deploy_app",
        "build_app", "rollback_app", "scale_app", "agent_turn",
        "receive_agent_events",
    }
    assert index["get_repository"].required == {"repository_id"}
    assert not index["list_repositories"].required, "the space is not a required input"
    assert index["list_repositories"].read and not index["create_repository"].read


def test_reads_run_as_the_person_in_their_space():
    fake = FakeLake()
    client = Scripted(message(tool_calls=[call("lake_read", capability="list_repositories")]),
                      message(content="You have one repository, site."))
    answer = run(client, fake)
    assert answer.reply == "You have one repository, site."
    sent = next(r for r in fake.requests if r.url.path == "/v1/list_repositories")
    assert sent.headers["Authorization"] == "Bearer person-key"
    assert sent.url.params["customer_id"] == "c-1"
    assert "list_repositories" in client.seen[0][0]["content"], "the index is in the prompt"


def test_a_change_is_proposed_never_executed():
    fake = FakeLake()
    client = Scripted(
        message(tool_calls=[call("lake_propose", capability="create_repository",
                                 input={"name": "notes"}, impact="Creates a repository notes")]),
        message(tool_calls=[call("lake_read", capability="create_repository", input={})]),
        message(content="I have proposed creating notes; confirm it to go ahead."))
    answer = run(client, fake)
    assert answer.proposals == [{"capability": "create_repository",
                                 "input": {"name": "notes", "customer_id": "c-1"},
                                 "impact": "Creates a repository notes"}]
    assert not any(r.method == "POST" and r.url.path == "/v1/create_repository"
                   for r in fake.requests), "nothing writes without the person's confirmation"


def test_it_delegates_through_lake_and_reports_the_agents_answer():
    fake = FakeLake()
    client = Scripted(
        message(tool_calls=[call("delegate", agent="agent-project", request="predict churn")]),
        message(content="The Project Agent built a churn Pipeline."))
    answer = run(client, fake)
    assert answer.delegations[0]["agent"] == "agent-project"
    assert answer.delegations[0]["ok"]
    sent = json.loads(next(r for r in fake.requests if r.url.path == "/v1/agent_turn").content)
    assert sent == {"customer_id": "c-1", "agent": "agent-project", "message": "predict churn",
                    "context": {}}
    # The subagent's task is followed on lake's agent bus until it finished.
    polls = [r for r in fake.requests if r.url.path == "/v1/receive_agent_events"]
    assert len(polls) == 2
    assert polls[1].url.params["from_sequence"] == "2", "each poll continues where the last stopped"
    assert answer.delegations[0]["answer"]["status"] == "succeeded"
    assert answer.delegations[0]["answer"]["answer"]["result"]["reply"] == "built a churn Pipeline"


def test_apps_are_listed_from_lake():
    fake = FakeLake()
    client = Scripted(
        message(tool_calls=[call("lake_read", capability="list_apps")]),
        message(content="You have one App, risk-console, and it is running."))
    answer = run(client, fake, message="What Apps do I have?")
    assert "prompt v10" in client.seen[0][0]["content"]
    assert answer.reads == [{
        "capability": "list_apps",
        "input": {"customer_id": "c-1"},
        "ok": True,
    }]
    assert "risk-console" in answer.reply


def test_app_health_uses_current_state_and_events():
    fake = FakeLake()
    client = Scripted(
        message(tool_calls=[
            call("lake_read", capability="get_app", input={"app_id": "app-1"}),
            call("lake_read", capability="receive_app_events",
                 input={"app_id": "app-1", "from_sequence": 1, "wait_ms": 0}),
        ]),
        message(content=(
            "risk-console is healthy: generation 4 is observed, ready, and Running. "
            "Its latest event also reports healthy."
        )))
    answer = run(client, fake, message="Is app-1 healthy?")
    assert [read["capability"] for read in answer.reads] == ["get_app", "receive_app_events"]
    assert "healthy" in answer.reply
    assert "generation 4" in answer.reply


def test_last_build_failure_uses_build_state_and_events():
    fake = FakeLake()
    client = Scripted(
        message(tool_calls=[call("lake_read", capability="list_builds")]),
        message(tool_calls=[
            call("lake_read", capability="get_build", input={"build_id": "build-9"}),
            call("lake_read", capability="receive_build_events",
                 input={"build_id": "build-9", "from_sequence": 1, "wait_ms": 0}),
        ]),
        message(content=(
            "The latest build, build-9, failed during dependency installation because the "
            "package lock is out of date."
        )))
    answer = run(client, fake, message="Why did the last build for app-1 fail?")
    assert [read["capability"] for read in answer.reads] == [
        "list_builds", "get_build", "receive_build_events",
    ]
    assert "package lock is out of date" in answer.reply


def test_app_work_is_an_app_turn_followed_through_lake():
    fake = FakeLake()
    client = Scripted(
        message(tool_calls=[call(
            "delegate",
            agent="agent-application",
            request="Build an App that shows the highest-risk accounts.",
            context={"page": "ship/apps"},
        )]),
        message(content=(
            "ApplicationAgent proposed the risk console App for your review; it has not been "
            "created yet."
        )))
    answer = run(client, fake, message="Build me a risk console App.")
    sent = json.loads(next(
        request.content
        for request in fake.requests
        if request.url.path == "/v1/agent_turn"
    ))
    assert sent == {
        "customer_id": "c-1",
        "agent": "agent-application",
        "message": "Build an App that shows the highest-risk accounts.",
        "context": {"page": "ship/apps"},
        "kind": "app",
    }
    assert answer.delegations[0]["kind"] == "app"
    assert answer.delegations[0]["answer"]["status"] == "succeeded"
    assert "has not been created" in answer.reply


def test_experiment_requests_use_the_registered_turn_kinds_and_summarize_results():
    cases = [
        (
            "Train a model on accounts.",
            "experiment",
            {"dataset": "accounts"},
            "ExperimentsAgent proposed minimizing validation loss over learning rate and max "
            "depth with a 12-trial budget. Review and confirm it in lake; no study has started.",
        ),
        (
            "Tune my churn model.",
            "experiment",
            {"project": "retention"},
            "ExperimentsAgent proposed a 12-trial tuning study. Review and confirm it in lake; "
            "no study has started.",
        ),
        (
            "Find the best model for retention.",
            "experiment",
            {"project": "retention"},
            "ExperimentsAgent proposed a best-model search with a 12-trial budget. Review and "
            "confirm it in lake; no study has started.",
        ),
        (
            "How is study-7 progressing?",
            "experiment_status",
            {"study": "study-7"},
            "ExperimentsAgent reports study-7 has completed 4 of its 12 budgeted trials.",
        ),
        (
            "Why did run-4 diverge?",
            "experiment_explain",
            {"run": "run-4"},
            "ExperimentsAgent reports run-4 diverged because its gradient norm became non-finite.",
        ),
    ]
    for user_message, turn_kind, context, summary in cases:
        fake = FakeLake()
        client = Scripted(
            message(tool_calls=[call(
                "delegate",
                agent="agent-experiments",
                kind=turn_kind,
                request=user_message,
                context=context,
            )]),
            message(content=summary),
        )
        answer = run(client, fake, message=user_message)
        sent = json.loads(next(
            request.content
            for request in fake.requests
            if request.url.path == "/v1/agent_turn"
        ))
        assert sent == {
            "customer_id": "c-1",
            "agent": "agent-experiments",
            "message": user_message,
            "context": context,
            "kind": turn_kind,
        }
        assert answer.delegations[0]["kind"] == turn_kind
        assert answer.delegations[0]["answer"]["status"] == "succeeded"
        assert answer.reply == summary
        experiment_calls = {
            request.url.path.removeprefix("/v1/")
            for request in fake.requests
            if request.url.path in {"/v1/agent_turn", "/v1/receive_agent_events"}
        }
        assert experiment_calls <= LAKE_MCP_TOOLS
        assert not any(request.url.path == "/v1/start_study" for request in fake.requests)


def test_experiments_agent_requires_a_registered_turn_kind():
    fake = FakeLake()
    client = Scripted(
        message(tool_calls=[call(
            "delegate",
            agent="agent-experiments",
            request="Train a model.",
        )]),
        message(content="I need to route that as an experiment turn."),
    )
    answer = run(client, fake, message="Train a model.")
    assert not answer.delegations
    assert not any(request.url.path == "/v1/agent_turn" for request in fake.requests)
    assert "requires one of these turn kinds" in client.seen[1][-1]["content"]


def test_ask_orama_cannot_forward_experiment_confirmation_objects():
    for field in ("confirmed_proposal", "confirmed_promotion"):
        fake = FakeLake()
        client = Scripted(
            message(tool_calls=[call(
                "delegate",
                agent="agent-experiments",
                kind="experiment",
                request="Apply the reviewed experiment change.",
                context={field: {"name": "retention tuning"}},
            )]),
            message(content="Confirm it in lake; I cannot apply it from chat."),
        )
        answer = run(client, fake, message="Yes, apply it.")
        assert not answer.delegations
        assert not any(request.url.path == "/v1/agent_turn" for request in fake.requests)
        assert "confirmation_owned_by_lake" in client.seen[1][-1]["content"]


def test_app_actions_are_proposed_and_never_sent():
    actions = [
        ("create_app", {"name": "risk-console"}),
        ("deploy_app", {"app_id": "app-1", "image": "risk-console:v2"}),
        ("build_app", {"app_id": "app-1"}),
        ("rollback_app", {"app_id": "app-1", "image": "risk-console:v1"}),
        ("scale_app", {"app_id": "app-1", "replicas": 2}),
    ]
    for capability, payload in actions:
        fake = FakeLake()
        client = Scripted(
            message(tool_calls=[call(
                "lake_propose",
                capability=capability,
                input=payload,
                impact=f"Proposes {capability} for risk-console",
            )]),
            message(content=f"I proposed {capability}; confirm it in lake."))
        answer = run(client, fake, message=f"Please {capability} for risk-console.")
        assert answer.proposals[0]["capability"] == capability
        assert not any(request.url.path == f"/v1/{capability}" for request in fake.requests)


def test_an_unknown_capability_is_an_observation():
    fake = FakeLake()
    client = Scripted(message(tool_calls=[call("lake_read", capability="drop_database")]),
                      message(content="That is not something lake can do."))
    run(client, fake)
    tool_reply = client.seen[1][-1]
    assert tool_reply["role"] == "tool" and "not a lake capability" in tool_reply["content"]


def test_which_model_scored_best_is_one_read_of_every_models_held_out_scores():
    """agent-ask-orama#14: the question answers within the round budget, from held-out scores."""
    fake = FakeLake()
    client = Scripted(
        message(tool_calls=[call("compare_models", project="API_churn")]),
        message(content="run two scored best: held-out AUC 0.890 against 0.874 for run one."))
    answer = run(client, fake, message="Which of my models in project api_churn scored best "
                                        "on held-out AUC?")
    assert answer.rounds == 2 and not answer.incomplete
    assert answer.reads == [{"capability": "workspace_query",
                             "input": {"capability": "list_models", "project": "API_churn"},
                             "ok": True}]
    sent = [json.loads(r.content) for r in fake.requests if r.url.path == "/v1/workspace_query"]
    assert sent == [{"capability": "list_models", "input": {}, "customer_id": "c-1"}]
    observed = json.loads(client.seen[1][-1]["content"])
    assert observed["ranked_by"] == "held_out_auc"
    assert observed["direction"] == "higher is better"
    assert observed["best"] == {"id": "m-2", "name": "churn model", "run": "run two",
                                "held_out_auc": 0.890}
    assert [m["id"] for m in observed["models"]] == ["m-2", "m-1", "m-3"], \
        "best first; the model with no holdout last; another project's left out"
    unscored = observed["models"][-1]
    assert unscored["held_out"] == {} and unscored["in_sample"]["auc"] == 0.99
    assert "did not hold rows out" in unscored["note"]


def test_compare_models_names_an_empty_project_and_a_failed_read():
    fake = FakeLake()
    client = Scripted(message(tool_calls=[call("compare_models", project="nothing")]),
                      message(content="That project has no models."))
    run(client, fake)
    observed = json.loads(client.seen[1][-1]["content"])
    assert observed["count"] == 0 and "no models in project 'nothing'" in observed["note"]

    def refusing(request):
        if request.url.path == "/v1/workspace_query":
            return httpx.Response(200, json={"ok": False, "error": {
                "code": "unknown_capability", "message": "list_models"}})
        return fake(request)

    client = Scripted(message(tool_calls=[call("compare_models")]),
                      message(content="I could not read the models."))
    answer = run(client, refusing)
    assert client.seen[1][-1]["content"].startswith("FAILED: unknown_capability")
    assert answer.reads[0]["ok"] is False


def test_a_turn_out_of_rounds_ends_unfinished_with_an_honest_partial_answer(tmp_path):
    """agent-ask-orama#14: running out of tool rounds is never a success."""
    fake = FakeLake()
    reads = [message(tool_calls=[call("lake_read", capability="list_repositories")])
             for _ in range(agent.MAX_ROUNDS)]
    client = Scripted(*reads, message(content="So far: one repository, site. Still unknown: "
                                              "its last build."))
    answer = run(client, fake)
    assert answer.incomplete and answer.rounds == agent.MAX_ROUNDS
    assert answer.reply.startswith("I did not finish this.")
    assert "one repository, site" in answer.reply
    assert "every tool round" in client.seen[-1][-1]["content"], "asked to answer without tools"

    # As a service turn it is not ok, so the bus publishes `failed` with the partial answer.
    state = service.State()
    state.trace_dir = tmp_path
    client = Scripted(*reads, message(content="I did not finish this. Nothing found yet."))
    result = service.run_turn({"message": "hi", "lake_token": "person-key",
                               "lake_url": "http://lake"}, state, client,
                              agent.Lake(turn(), transport=httpx.MockTransport(fake)))
    assert result["ok"] is False and result["incomplete"] is True
    assert result["error"] == "I did not finish this. Nothing found yet."


def test_an_empty_or_failed_partial_answer_still_says_it_did_not_finish():
    fake = FakeLake()
    reads = [message(tool_calls=[call("lake_read", capability="list_repositories")])
             for _ in range(agent.MAX_ROUNDS)]
    answer = run(Scripted(*reads, message(content="")), fake)
    assert answer.incomplete and answer.reply == agent.OUT_OF_ROUNDS_FALLBACK
    answer = run(Scripted(*reads), fake)  # the final call itself fails
    assert answer.incomplete and answer.reply == agent.OUT_OF_ROUNDS_FALLBACK


def test_the_model_score_eval_needs_list_models_held_out_scores_and_a_finished_turn():
    from agent_ask_orama import evals
    index = agent.capability_index(OPENAPI)
    case = next(c for c in evals.generate(index) if c.kind == "model_scores")
    read = {"capability": "workspace_query", "input": {"capability": "list_models"}, "ok": True}
    good = {"reply": "run two scored best: held-out AUC 0.890.", "reads": [read],
            "proposals": [], "delegations": []}
    assert evals.grade(case, good, index, []).passed
    unfinished = {**good, "incomplete": True}
    assert "ran out of tool rounds before answering" in evals.grade(
        case, unfinished, index, []).reasons
    in_sample = {**good, "reply": "run three is best with AUC 0.99."}
    assert not evals.grade(case, in_sample, index, []).passed


def test_a_service_turn_needs_the_persons_key_and_keeps_the_conversation(tmp_path):
    state = service.State()
    state.trace_dir = tmp_path
    refused = service.run_turn({"message": "hi"}, state)
    assert not refused["ok"]
    fake = FakeLake()
    body = {"message": "hi", "lake_token": "person-key", "lake_url": "http://lake",
            "conversation_id": "conv-1"}
    first = service.run_turn(body, state, Scripted(message(content="Hello.")),
                             agent.Lake(turn(), transport=httpx.MockTransport(fake)))
    second = service.run_turn({**body, "message": "again"}, state,
                              Scripted(message(content="Hello again.")),
                              agent.Lake(turn(), transport=httpx.MockTransport(fake)))
    assert first["ok"] and second["ok"]
    assert len(state.history("conv-1")) == 5, "system, two people's turns, two replies"
    trace = (tmp_path / f"{second['trace_id']}.json").read_text()
    assert "person-key" not in trace


def test_evals_are_generated_from_the_index_and_graded_by_rules():
    from agent_ask_orama import evals
    index = agent.capability_index(OPENAPI)
    cases = evals.generate(index, changes=2, reads=2, clarify=2)
    kinds = {case.kind for case in cases}
    assert kinds == {
        "change",
        "read",
        "clarify",
        "delegate",
        "experiment",
        "experiment_status",
        "experiment_explain",
        "app_list",
        "app_health",
        "build_failure",
        "methodology",
        "solution",
        "solution_readout",
        "model_scores",
    }
    assert all(not index[c.expect].required for c in cases if c.kind in {"change", "read"}), \
        "a change or read case can be done as asked"
    change = next(case for case in cases if case.kind == "change")
    good = {"reply": "", "reads": [], "delegations": [],
            "proposals": [{"capability": change.expect, "input": {}, "impact": ""}]}
    assert evals.grade(change, good, index, []).passed
    assert not evals.grade(change, good, index, ["/v1/" + change.expect]).passed, \
        "a write sent without confirmation fails the case"
    invented = {**good, "proposals": [{"capability": "invented_thing", "input": {}, "impact": ""}]}
    assert not evals.grade(change, invented, index, []).passed

    clarify = next(case for case in cases if case.kind == "clarify")
    nothing = {"reply": "", "reads": [], "proposals": [], "delegations": []}
    asked = {**nothing, "reply": "Which item should I use?"}
    assert evals.grade(clarify, asked, index, []).passed, "asking for the id passes"
    found = {**nothing, "reads": [{"capability": "list_repositories"},
                                  {"capability": clarify.expect}]}
    assert evals.grade(clarify, found, index, []).passed, "finding the id, then reading, passes"
    guessed = {**nothing, "reads": [{"capability": clarify.expect}]}
    assert not evals.grade(clarify, guessed, index, []).passed, "a guessed id fails"
    silent = {**nothing, "reply": "Done."}
    assert not evals.grade(clarify, silent, index, []).passed

    app_list = next(case for case in cases if case.kind == "app_list")
    listed = {**nothing, "reads": [{"capability": "list_apps"}]}
    assert evals.grade(app_list, listed, index, []).passed
    app_health = next(case for case in cases if case.kind == "app_health")
    health = {**nothing, "reads": [
        {"capability": "get_app"},
        {"capability": "receive_app_events"},
    ]}
    assert evals.grade(app_health, health, index, []).passed
    assert not evals.grade(app_health, listed, index, []).passed
    build_failure = next(case for case in cases if case.kind == "build_failure")
    failed_build = {**nothing, "reads": [
        {"capability": "list_builds"},
        {"capability": "get_build"},
        {"capability": "receive_build_events"},
    ]}
    assert evals.grade(build_failure, failed_build, index, []).passed
    app_delegate = next(
        case
        for case in cases
        if case.kind == "delegate" and case.expect == "agent-application"
    )
    delegated = {**nothing, "delegations": [{"agent": "agent-application", "kind": "app"}]}
    assert evals.grade(app_delegate, delegated, index, []).passed
    wrong_kind = {**nothing, "delegations": [{"agent": "agent-application", "kind": None}]}
    assert not evals.grade(app_delegate, wrong_kind, index, []).passed

    experiment_cases = [
        case
        for case in cases
        if case.kind in {"experiment", "experiment_status", "experiment_explain"}
    ]
    replies = {
        "experiment": "ExperimentsAgent proposed a study; review and confirm it in lake.",
        "experiment_status": "Study study-7 has completed four trials within its budget.",
        "experiment_explain": "Run run-4 diverged after its gradient norm became non-finite.",
    }
    for experiment_case in experiment_cases:
        delegated = {
            **nothing,
            "reply": replies[experiment_case.kind],
            "delegations": [{
                "agent": "agent-experiments",
                "kind": experiment_case.kind,
            }],
        }
        assert evals.grade(experiment_case, delegated, index, []).passed
        wrong_kind = {
            **delegated,
            "delegations": [{"agent": "agent-experiments", "kind": "experiment"}],
        }
        if experiment_case.kind != "experiment":
            assert not evals.grade(experiment_case, wrong_kind, index, []).passed

    catalog = agent.MethodologyCatalog(
        methodologies={item["id"]: item for item in METHODOLOGIES},
        loaded=True,
    )
    methodology_read = {"capability": "workspace_query", "input": {
        "capability": "list_methodologies", "input": {}}, "ok": True}
    segmentation = next(case for case in cases if case.expect == "M-3")
    supported = {**nothing, "reply": "Yes, M-3 segmentation is runnable.",
                 "reads": [methodology_read]}
    assert evals.grade(segmentation, supported, index, [], catalog).passed
    speech = next(case for case in cases if case.expect == "M-14")
    missing_issue = {**nothing, "reply": "Speech is not supported yet.",
                     "reads": [methodology_read]}
    assert not evals.grade(speech, missing_issue, index, [], catalog).passed
    wrong_support = {**missing_issue, "reply": "Yes, speech is supported; see zetta#1053."}
    assert not evals.grade(speech, wrong_support, index, [], catalog).passed
    named_issue = {**missing_issue, "reply": "Speech is not supported yet; see zetta#1053."}
    assert evals.grade(speech, named_issue, index, [], catalog).passed

    solutions = agent.SolutionCatalog(
        solutions={item["id"]: item for item in SOLUTIONS},
        loaded=True,
    )
    solution_read = {"capability": "workspace_query", "input": {
        "capability": "list_solutions", "input": {}}, "ok": True}
    runnable = next(case for case in cases if case.expect == "S-1")
    available = {**nothing, "reply": "Yes, S-1 is runnable in production.",
                 "reads": [solution_read]}
    assert evals.grade(runnable, available, index, [], solutions=solutions).passed
    sketch = next(case for case in cases if case.expect == "B-1")
    declined = {**nothing, "reply": (
        "B-1 is a sketch and cannot be built; add supported methodology callbacks."
    ), "reads": [solution_read]}
    assert evals.grade(sketch, declined, index, [], solutions=solutions).passed
    readout = next(case for case in cases if case.kind == "solution_readout")
    measured = {**nothing, "reply": "There is not enough measured evidence yet.", "reads": [
        solution_read,
        {"capability": "workspace_query", "input": {
            "capability": "get_roi_readout", "input": {"project": "retention"}}, "ok": True},
    ]}
    assert evals.grade(readout, measured, index, [], solutions=solutions).passed


def test_a_read_that_takes_no_space_is_sent_without_one():
    # Live eval 2026-09-27: identity refused "unexpected field customer_id" on every try.
    index = agent.capability_index(OPENAPI)
    assert not index["identity"].takes_customer and index["list_repositories"].takes_customer
    assert index["create_repository"].takes_customer
    fake = FakeLake()
    client = Scripted(message(tool_calls=[call("lake_read", capability="identity")]),
                      message(content="This lake is taap:lake."))
    answer = run(client, fake)
    sent = next(r for r in fake.requests if r.url.path == "/v1/identity")
    assert "customer_id" not in sent.url.params
    assert answer.reads and answer.reply == "This lake is taap:lake."


def test_a_subagent_still_working_when_the_budget_ends_is_reported_as_working():
    fake = FakeLake()
    fake.polls = -100  # it never finishes within this test
    lake = agent.Lake(agent.Turn(message="m", lake_url="http://lake", lake_token="k",
                                 customer_id="c-1", page={}, conversation_id="x"),
                      transport=httpx.MockTransport(fake))
    ticks = iter([0.0, 5.0, 10.0])
    followed = agent.follow(lake, "c-1", "t-1", budget=8.0, clock=lambda: next(ticks))
    assert followed["ok"] and followed["value"]["status"] == "running"


def test_a_post_that_only_reads_is_read_not_proposed():
    """UX review 2026-09-27: workspace_query (a POST) was taken for a change, so Ask Orama never
    read the workspace and guessed SQL instead."""
    index = agent.capability_index(OPENAPI)
    assert index["workspace_query"].read and not index["workspace_query"].get
    assert not index["create_repository"].read
    fake = FakeLake()
    client = Scripted(
        message(tool_calls=[call("lake_read", capability="workspace_query",
                                 input={"capability": "list_datasets", "input": {}})]),
        message(content="You have one dataset, accounts (200 rows)."))
    answer = run(client, fake)
    sent = [r for r in fake.requests if r.url.path == "/v1/workspace_query"]
    assert sent and sent[0].method == "POST"
    assert json.loads(sent[0].content)["capability"] == "list_datasets"
    assert answer.reads == [{"capability": "workspace_query", "input": {
        "customer_id": "c-1", "capability": "list_datasets", "input": {}}, "ok": True}]


def test_a_runnable_methodology_can_be_proposed_after_reading_the_registry():
    fake = FakeLake()
    client = Scripted(
        message(tool_calls=[call("lake_read", capability="workspace_query", input={
            "capability": "list_methodologies", "input": {}})]),
        message(tool_calls=[call("lake_propose", capability="workspace_act", input={
            "capability": "compile_intent",
            "input": {"project": "segments", "intent": "segment customers",
                      "methodology": "M-3"}},
            impact="Recompiles segments as an M-3 Pipeline")]),
        message(content="I proposed the runnable M-3 segmentation Pipeline."))
    answer = run(client, fake, message="Can you segment my customers?")
    assert "prompt v10" in client.seen[0][0]["content"]
    assert answer.proposals == [{
        "capability": "workspace_act",
        "input": {
            "customer_id": "c-1",
            "capability": "compile_intent",
            "input": {"project": "segments", "intent": "segment customers",
                      "methodology": "M-3"},
        },
        "impact": "Recompiles segments as an M-3 Pipeline",
    }]


def test_an_unsupported_methodology_is_declined_with_its_issue():
    fake = FakeLake()
    client = Scripted(
        message(tool_calls=[call("lake_read", capability="workspace_query", input={
            "capability": "list_methodologies", "input": {}})]),
        message(tool_calls=[call("lake_propose", capability="workspace_act", input={
            "capability": "compile_intent",
            "input": {"project": "calls", "intent": "analyze speech",
                      "methodology": "M-14"}},
            impact="Recompiles calls as an M-14 Pipeline")]),
        message(content="Speech analytics is not supported yet; see zetta#1053."))
    answer = run(client, fake, message="Can you do speech analytics?")
    assert not answer.proposals
    assert "zetta#1053" in answer.reply
    refusal = client.seen[2][-1]["content"]
    assert "not_supported" in refusal
    assert "https://github.com/oramasearch/zetta/issues/1053" in refusal
    assert not any(request.url.path == "/v1/workspace_act" for request in fake.requests)


def test_an_old_engine_falls_back_to_m1_only():
    fake = FakeLake({
        "ok": False,
        "error": {"code": "unknown_capability", "message": "unknown list_methodologies"},
    })
    client = Scripted(
        message(tool_calls=[call("lake_read", capability="workspace_query", input={
            "capability": "list_methodologies", "input": {}})]),
        message(content="This older engine only runs M-1 churn / GBDT classification."))
    answer = run(client, fake, message="Can you do speech analytics?")
    assert answer.reply == "This older engine only runs M-1 churn / GBDT classification."
    fallback = client.seen[1][-1]["content"]
    assert "Only M-1 runs" in fallback
    assert "zetta#1061" in fallback


def test_a_runnable_solution_is_read_from_the_registry_and_proposed():
    fake = FakeLake()
    client = Scripted(
        message(tool_calls=[call("lake_read", capability="workspace_query", input={
            "capability": "list_solutions", "input": {}})]),
        message(tool_calls=[call("lake_read", capability="workspace_query", input={
            "capability": "get_solution", "input": {"solution": "S-1"}})]),
        message(tool_calls=[call("lake_propose", capability="workspace_act", input={
            "capability": "create_solution",
            "input": {"project": "retention", "solution": "S-1", "level": 1,
                      "sources": {"source": "datasets", "table": "customers"}}},
            impact="Builds the S-1 level 1 Pipeline in retention")]),
        message(content="I proposed the S-1 level 1 Pipeline for your confirmation."))
    answer = run(client, fake, message="Build S-1 level 1 in retention from customers.")
    assert "prompt v10" in client.seen[0][0]["content"]
    detail = client.seen[2][-1]["content"]
    assert "Customer retention" in detail
    assert "minimum_level" in detail
    assert "data_roles" in detail
    assert answer.proposals == [{
        "capability": "workspace_act",
        "input": {
            "customer_id": "c-1",
            "capability": "create_solution",
            "input": {"project": "retention", "solution": "S-1", "level": 1,
                      "sources": {"source": "datasets", "table": "customers"}},
        },
        "impact": "Builds the S-1 level 1 Pipeline in retention",
    }]
    assert not any(request.url.path == "/v1/workspace_act" for request in fake.requests)


def test_a_solution_with_missing_components_is_described_as_a_preview():
    fake = FakeLake()
    client = Scripted(
        message(tool_calls=[call("lake_read", capability="workspace_query", input={
            "capability": "list_solutions", "input": {}})]),
        message(tool_calls=[call("lake_read", capability="workspace_query", input={
            "capability": "get_solution", "input": {"solution": "S-2"}})]),
        message(content=(
            "The pipeline builds as a preview; production operation needs the decision policy "
            "engine (zetta#1104) and measured-value readout (zetta#1108)."
        )))
    answer = run(client, fake, message="Is S-2 ready to use?")
    detail = client.seen[2][-1]["content"]
    assert '"runnable": false' in detail
    assert "decision policy engine" in detail
    assert "zetta#1108" in detail
    assert "pipeline builds" in answer.reply
    assert "production operation needs" in answer.reply


def test_a_solution_sketch_is_refused_with_its_promotion_condition():
    fake = FakeLake()
    client = Scripted(
        message(tool_calls=[call("lake_read", capability="workspace_query", input={
            "capability": "list_solutions", "input": {}})]),
        message(tool_calls=[call("lake_propose", capability="workspace_act", input={
            "capability": "create_solution",
            "input": {"project": "procurement", "solution": "B-1", "level": 1,
                      "sources": {"source": "datasets", "table": "purchases"}}},
            impact="Builds the B-1 Pipeline")]),
        message(content=(
            "B-1 is a sketch and cannot be built; promotion needs supported methodology "
            "callbacks and is tracked by zetta#1102."
        )))
    answer = run(client, fake, message="Build B-1 for procurement.")
    assert not answer.proposals
    refusal = client.seen[2][-1]["content"]
    assert "not_supported" in refusal
    assert "add supported methodology callbacks" in refusal
    assert "https://github.com/oramasearch/zetta/issues/1102" in refusal
    assert not any(request.url.path == "/v1/workspace_act" for request in fake.requests)


def test_an_engine_without_the_solution_registry_uses_methodologies_only():
    fake = FakeLake(solution_response={
        "ok": False,
        "error": {"code": "unknown_capability", "message": "unknown list_solutions"},
    })
    client = Scripted(
        message(tool_calls=[call("lake_read", capability="workspace_query", input={
            "capability": "list_solutions", "input": {}})]),
        message(content=(
            "This engine does not have solution operations deployed yet; I can check its "
            "methodologies instead."
        )))
    answer = run(client, fake, message="Which solutions can I build?")
    assert "solution operations" in answer.reply
    fallback = client.seen[1][-1]["content"]
    assert "predates list_solutions" in fallback
    assert "Methodology support may still be available" in fallback


def test_solution_policy_ledger_monitor_and_readout_are_read_after_the_registry():
    fake = FakeLake()
    client = Scripted(
        message(tool_calls=[call("lake_read", capability="workspace_query", input={
            "capability": "list_solutions", "input": {}})]),
        message(tool_calls=[
            call("lake_read", capability="workspace_query", input={
                "capability": capability, "input": {"project": "retention"}})
            for capability in (
                "get_policy",
                "get_experiment",
                "list_ledger",
                "get_monitor",
                "get_roi_readout",
            )
        ]),
        message(content=(
            "Retention uses policy version 3 and its monitor is healthy. The holdout is still "
            "collecting, the ledger has a pending reviewed action, and the measured-value "
            "readout has insufficient evidence, so there is no return figure to report."
        )))
    answer = run(client, fake, message="Show retention's policy, evidence and measured readout.")
    inner = [
        read["input"]["capability"]
        for read in answer.reads
        if read["capability"] == "workspace_query"
    ]
    assert inner == [
        "list_solutions",
        "get_policy",
        "get_experiment",
        "list_ledger",
        "get_monitor",
        "get_roi_readout",
    ]
    assert "insufficient evidence" in answer.reply
    assert "no return figure" in answer.reply


def test_a_policy_change_is_proposed_and_never_sent():
    fake = FakeLake()
    client = Scripted(
        message(tool_calls=[call("lake_read", capability="workspace_query", input={
            "capability": "list_solutions", "input": {}})]),
        message(tool_calls=[call("lake_read", capability="workspace_query", input={
            "capability": "get_policy", "input": {"project": "retention"}})]),
        message(tool_calls=[call("lake_propose", capability="workspace_act", input={
            "capability": "update_policy",
            "input": {"project": "retention", "changes": {"review_threshold": "high"}}},
            impact="Requires review for every high-risk retention action")]),
        message(content="I proposed the policy change for your confirmation; it is not active."))
    answer = run(client, fake, message="Require review for every high-risk retention action.")
    assert answer.proposals[0]["input"]["capability"] == "update_policy"
    assert "not active" in answer.reply
    assert not any(request.url.path == "/v1/workspace_act" for request in fake.requests)


def test_a_solution_operation_requires_this_turns_registry_read():
    fake = FakeLake()
    client = Scripted(
        message(tool_calls=[call("lake_propose", capability="workspace_act", input={
            "capability": "update_policy",
            "input": {"project": "retention", "changes": {"review_threshold": "high"}}},
            impact="Requires review for every high-risk retention action")]),
        message(content="I need to read the current solution registry first."))
    answer = run(client, fake, message="Change retention's review threshold.")
    assert not answer.proposals
    assert "solution_registry_required" in client.seen[1][-1]["content"]
    assert not any(request.url.path == "/v1/workspace_act" for request in fake.requests)


def test_an_unknown_solution_operation_is_reported_as_not_deployed():
    fake = FakeLake(solution_operations={
        "get_monitor": {"ok": False, "error": {
            "code": "unknown_capability", "message": "unknown get_monitor"}},
    })
    client = Scripted(
        message(tool_calls=[call("lake_read", capability="workspace_query", input={
            "capability": "list_solutions", "input": {}})]),
        message(tool_calls=[call("lake_read", capability="workspace_query", input={
            "capability": "get_monitor", "input": {"project": "retention"}})]),
        message(content="The solution monitor operation is not deployed yet."))
    answer = run(client, fake, message="How is retention's monitor?")
    assert "not deployed yet" in answer.reply
    assert "unknown_capability" in client.seen[2][-1]["content"]


def test_the_prompt_offers_no_internal_agent() -> None:
    # lake#451: Eval Generator and the corpus generators are Orama's own tooling, not agents a
    # person delegates to; lake hides them from Talk to and the prompt must not offer them either.
    from agent_ask_orama.agent import PROMPT_VERSION
    from pathlib import Path

    import agent_ask_orama

    prompt = (Path(agent_ask_orama.__file__).parent / "prompts" / f"{PROMPT_VERSION}.md").read_text()
    for internal in ("agent-eval-generator", "agent-autosuggest-corpus", "agent-project-corpus"):
        assert internal not in prompt

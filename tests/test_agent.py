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
    "/v1/workspace_query": {"get": {"summary": "Query a workspace", "parameters": CUSTOMER}},
    "/v1/create_repository": {"post": {"summary": "Create a repository",
                                       "requestBody": body("customer_id", "name")}},
    "/v1/agent_turn": {"post": {"summary": "Talk to an agent",
                                "requestBody": body("customer_id", "agent", "message")}},
    "/v1/sign_in_password": {"post": {"summary": "Sign in"}},
    "/v1/repositories/{id}/sync/push": {"post": {"summary": "binary"}},
}}


class FakeLake:
    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.polls = 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.url.path == "/v1/openapi.json":
            return httpx.Response(200, json=OPENAPI)
        if request.url.path == "/v1/list_repositories":
            return httpx.Response(200, json={"ok": True, "value": {"items": [{"name": "site"}]}})
        if request.url.path == "/v1/identity":
            if "customer_id" in request.url.params:
                return httpx.Response(400, json={"ok": False, "error": {
                    "code": "invalid_input", "message": "unexpected field customer_id"}})
            return httpx.Response(200, json={"ok": True, "value": {"id": "taap:lake"}})
        if request.url.path == "/v1/agent_turn":
            sent = json.loads(request.content)
            if sent["agent"] == "agent-project":
                # A library agent: the turn is a task on lake's agent bus (lake#269).
                return httpx.Response(200, json={"ok": True, "value": {
                    "task_id": "t-1", "agent": "agent-project", "status": "pending"}})
            return httpx.Response(200, json={"ok": True, "value": {
                "agent": sent["agent"], "reply": "built a churn Pipeline"}})
        if request.url.path == "/v1/receive_agent_events":
            self.polls += 1
            status = "running" if self.polls < 2 else "succeeded"
            answer = {"ok": True, "result": {"reply": "built a churn Pipeline"}}
            return httpx.Response(200, json={"ok": True, "value": {
                "events": [], "next_sequence": self.polls + 1,
                "task": {"task_id": "t-1", "agent": "agent-project", "status": status,
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
    assert set(index) == {"list_repositories", "identity", "get_repository", "workspace_query",
                          "create_repository", "agent_turn"}
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


def test_an_unknown_capability_is_an_observation():
    fake = FakeLake()
    client = Scripted(message(tool_calls=[call("lake_read", capability="drop_database")]),
                      message(content="That is not something lake can do."))
    run(client, fake)
    tool_reply = client.seen[1][-1]
    assert tool_reply["role"] == "tool" and "not a lake capability" in tool_reply["content"]


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
    assert kinds == {"change", "read", "clarify", "delegate"}
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
    assert clarify.expect == "get_repository"
    nothing = {"reply": "", "reads": [], "proposals": [], "delegations": []}
    asked = {**nothing, "reply": "Which repository should I get?"}
    assert evals.grade(clarify, asked, index, []).passed, "asking for the id passes"
    found = {**nothing, "reads": [{"capability": "list_repositories"},
                                  {"capability": "get_repository"}]}
    assert evals.grade(clarify, found, index, []).passed, "finding the id, then reading, passes"
    guessed = {**nothing, "reads": [{"capability": "get_repository"}]}
    assert not evals.grade(clarify, guessed, index, []).passed, "a guessed id fails"
    silent = {**nothing, "reply": "Done."}
    assert not evals.grade(clarify, silent, index, []).passed


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

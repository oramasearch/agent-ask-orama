"""Task credentials by reference (lake#871, lake docs/api/agent-bus.md).

A claim asks Lake for `credentials: by_reference`: the body arrives with no credential, and every
call made for the task carries this agent's bus credential and `X-Lake-Agent-Task: <task id>`. A
Lake from before lake#871 refuses the field; the claim is asked again and the body's own credential
is used, as before.
"""

from __future__ import annotations

import json
import threading
import urllib.parse
from typing import Any

import httpx

from agent_ask_orama import agent, lake_bus, model, service
from test_agent import FakeLake as FakeWorkspaceLake
from test_agent import openai_answer

TASK = {"task_id": "t1", "customer_id": "c", "workspace_id": "w", "kind": "ask"}


class BusLake:
    """lake's bus in memory. `supports_by_reference` False is a Lake from before lake#871."""

    def __init__(self, supports_by_reference: bool) -> None:
        self.supports_by_reference = supports_by_reference
        self.claims: list[dict[str, Any]] = []
        self.headers: list[dict[str, str]] = []
        self.stop = threading.Event()
        self.received = False

    def send(self, method: str, url: str, headers: dict[str, str],
             body: bytes | None) -> tuple[int, str]:
        self.headers.append(headers)
        capability = urllib.parse.urlparse(url).path.rsplit("/", 1)[-1]
        if capability == "receive_agent_tasks":
            tasks = [] if self.received else [{"sequence": 1, **TASK}]
            self.received = True
            if not tasks:
                self.stop.set()
            return 200, json.dumps({"ok": True, "value": {"tasks": tasks, "next_sequence": 2}})
        arguments = json.loads(body or b"{}")
        if capability == "claim_agent_task":
            self.claims.append(arguments)
            if "credentials" in arguments and not self.supports_by_reference:
                return 400, json.dumps({"ok": False, "error": {
                    "code": "invalid_input", "message": "unexpected field credentials",
                    "path": "/credentials"}})
            by_reference = arguments.get("credentials") == "by_reference"
            credential = "" if by_reference else "lat.t1.secret"
            value = {**TASK, "body": {"message": "hi", "lake_token": credential}}
            if by_reference:
                value["credentials"] = "by_reference"
            return 200, json.dumps({"ok": True, "value": value})
        return 200, json.dumps({"ok": True, "value": {}})


def handed_body(lake: BusLake) -> dict[str, Any]:
    handed: list[dict[str, Any]] = []
    bus = lake_bus.LakeBus("http://lake", "bus-token", "agent-ask-orama", send=lake.send)
    lake_bus.work(bus, lambda body: handed.append(body) or {"ok": True}, lake.stop, workers=1)
    assert len(handed) == 1, handed
    return handed[0]


def test_a_claim_asks_by_reference_and_the_turn_holds_no_task_credential():
    lake = BusLake(supports_by_reference=True)
    body = handed_body(lake)
    assert lake.claims == [{"task_id": "t1", "agent": "agent-ask-orama",
                            "credentials": "by_reference"}]
    assert body["lake_token"] == "bus-token", "the turn calls Lake with the bus credential"
    assert body["lake_headers"] == {"X-Lake-Agent-Task": "t1"}
    assert lake_bus.task_headers(body) == {"X-Lake-Agent-Task": "t1"}
    # Bus calls themselves never name a task: Lake would answer them as the task.
    assert all(lake_bus.TASK_HEADER not in headers for headers in lake.headers)


def test_a_lake_from_before_by_reference_is_claimed_again_with_the_credential_in_the_body():
    lake = BusLake(supports_by_reference=False)
    body = handed_body(lake)
    assert lake.claims == [
        {"task_id": "t1", "agent": "agent-ask-orama", "credentials": "by_reference"},
        {"task_id": "t1", "agent": "agent-ask-orama"},
    ]
    assert body["lake_token"] == "lat.t1.secret", "the body's own credential is used, as before"
    assert "lake_headers" not in body
    assert lake_bus.task_headers(body) == {}


def test_a_claim_refused_for_another_reason_is_not_asked_again():
    error = lake_bus.BusError("invalid_input", "task_id is required")
    assert not lake_bus.refuses_by_reference(error)
    assert lake_bus.refuses_by_reference(
        lake_bus.BusError("invalid_input", "unexpected field credentials"))


def test_task_headers_take_only_the_task_header():
    assert lake_bus.task_headers({"lake_headers": {"X-Lake-Agent-Task": "t1",
                                                   "Authorization": "Bearer other"}}) == {
        "X-Lake-Agent-Task": "t1"}
    assert lake_bus.task_headers({"lake_headers": "t1"}) == {}
    assert lake_bus.task_headers({}) == {}


def test_every_call_for_a_by_reference_turn_names_its_task(tmp_path, monkeypatch):
    """The turn's Lake reads and its model calls carry the bus credential and the task header."""
    seen: list[httpx.Request] = []

    def gateway(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=openai_answer("Hello."))

    fake = FakeWorkspaceLake()
    real = httpx.Client

    def client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(fake)
        return real(*args, **kwargs)

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(agent.httpx, "Client", client)
    monkeypatch.setattr(service, "gateway_client", lambda url, token, **kw: model.gateway_client(
        url, token, http_client=real(transport=httpx.MockTransport(gateway)), **kw))
    state = service.State()
    state.trace_dir = tmp_path
    state.lake_url = "http://lake:8080"
    claimed = {**TASK, "credentials": "by_reference",
               "body": {"message": "hi", "lake_token": ""}}
    result = service.run_turn(lake_bus.turn_body(claimed, "bus-token"), state, claim=TASK)
    assert result["ok"], result
    assert seen and fake.requests
    for request in [*seen, *fake.requests]:
        assert request.headers["authorization"] == "Bearer bus-token"
        assert request.headers["x-lake-agent-task"] == "t1"


def test_a_turn_with_its_credential_in_the_body_sends_no_task_header(tmp_path, monkeypatch):
    seen: list[httpx.Request] = []

    def gateway(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=openai_answer("Hello."))

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(service, "gateway_client", lambda url, token, **kw: model.gateway_client(
        url, token, http_client=httpx.Client(transport=httpx.MockTransport(gateway)), **kw))
    state = service.State()
    state.trace_dir = tmp_path
    state.lake_url = "http://lake:8080"
    claimed = {**TASK, "body": {"message": "hi", "lake_token": "lat.t1.secret"}}
    result = service.run_turn(lake_bus.turn_body(claimed, "bus-token"), state, claim=TASK,
                              lake=agent.Lake(agent.Turn(message="hi", lake_url="http://lake:8080",
                                                         lake_token="lat.t1.secret"),
                                              transport=httpx.MockTransport(FakeWorkspaceLake())))
    assert result["ok"], result
    assert seen[0].headers["authorization"] == "Bearer lat.t1.secret"
    assert "x-lake-agent-task" not in seen[0].headers

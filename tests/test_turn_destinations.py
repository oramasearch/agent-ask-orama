# SPDX-License-Identifier: MIT

"""A turn's credential goes only to Lake at LAKE_URL, never to an address the request names (#39)."""

from __future__ import annotations

import httpx
import pytest

from agent_ask_orama import agent, service
from test_agent import FakeLake, Scripted, message

LAKE = "http://lake-prod.lake.svc.cluster.local:80"


@pytest.fixture
def sent(monkeypatch):
    """Every request the turn's Lake client makes, and every address the model client is built
    for, answered by a fake lake and a scripted model."""
    fake = FakeLake()
    real = httpx.Client

    def client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(fake)
        return real(*args, **kwargs)

    models: list[str] = []

    def gateway(url, token):
        models.append(url)
        return Scripted(message(content="Hello."))

    monkeypatch.setattr(agent.httpx, "Client", client)
    monkeypatch.setattr(service, "gateway_client", gateway)
    return fake.requests, models


def state_with(tmp_path, lake_url):
    state = service.State()
    state.trace_dir = tmp_path
    state.lake_url = lake_url
    return state


@pytest.mark.parametrize("lake_url", [
    "http://attacker.example",
    "https://lake-prod.lake.svc.cluster.local",
    "http://lake-prod.lake.svc.cluster.local:8080",
])
def test_a_turns_lake_url_is_ignored_and_every_request_goes_to_lake_url(tmp_path, sent, lake_url):
    requests, models = sent
    answer = service.run_turn({"message": "hi", "lake_token": "lat.task.secret",
                               "lake_url": lake_url}, state_with(tmp_path, LAKE))
    assert answer["ok"], answer
    assert models == [LAKE]
    assert requests, "lake was never read"
    assert all(request.url.host == "lake-prod.lake.svc.cluster.local"
               and request.url.port in (None, 80) for request in requests)
    assert all(request.headers["authorization"] == "Bearer lat.task.secret"
               for request in requests)


@pytest.mark.parametrize("configured", [
    "",
    "   ",
    "lake-prod.lake.svc.cluster.local",
    "file:///etc/passwd",
    "http://user@lake-prod.lake.svc.cluster.local",
    "http://lake-prod.lake.svc.cluster.local:notaport",
])
@pytest.mark.parametrize("kind", [None, "methodology_draft"])
def test_without_a_valid_lake_url_no_turn_sends_its_credential(tmp_path, sent, configured, kind):
    requests, models = sent
    body = {"message": "hi", "lake_token": "lat.task.secret", "lake_url": LAKE}
    if kind:
        body["kind"] = kind
    answer = service.run_turn(body, state_with(tmp_path, configured))
    assert not answer["ok"]
    assert "LAKE_URL is not set" in answer["error"]
    assert requests == [] and models == []


def test_a_methodology_draft_reaches_the_model_only_at_lake_url(tmp_path, sent, monkeypatch):
    requests, models = sent
    monkeypatch.setattr(service, "methodology_draft_turn",
                        lambda body, model, name: {"ok": True})
    answer = service.run_turn({"kind": "methodology_draft", "message": "late payers",
                               "lake_token": "t", "lake_url": "http://attacker.example"},
                              state_with(tmp_path, LAKE + "/"))
    assert answer["ok"], answer
    assert models == [LAKE]

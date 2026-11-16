# SPDX-License-Identifier: MIT

"""Ask Orama's methodology_draft turn (lake#688), without a network: the model is scripted and the
package index is a fake (or an httpx MockTransport)."""

from __future__ import annotations

import json
from types import SimpleNamespace

import httpx

from agent_ask_orama import methodology_draft as md
from agent_ask_orama import service

SOURCE = '''import math, pickle


def fit(data, params):
    return pickle.dumps({"rate": params["learning_rate"]})


def predict(artifact, data):
    return [0.5 for _ in data.rows]


def score(artifact, data):
    return {"auc": 0.5, "log_loss": math.log(2)}
'''

MANIFEST = {
    "name": "Late payers",
    "description": "Which customers will pay late.",
    "inputs": {"kinds": ["tabular"], "target": {"required": True, "kind": "binary"},
               "required_features": []},
    "parameters": [{"name": "learning_rate", "kind": "float", "default": 0.1, "minimum": 0.001,
                    "maximum": 1, "log": True}],
    "metrics": ["auc", "log_loss"],
    "explain": False,
    "resources": {"cpu": "1", "memory": "2Gi", "gpu": 0, "timeout_seconds": 3600},
}
HASH = "a" * 64
HASH2 = "b" * 64


def answer(content: str):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


class Scripted:
    def __init__(self, *replies: dict | str) -> None:
        self.replies = [r if isinstance(r, str) else json.dumps(r) for r in replies]
        self.seen: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.seen.append(kwargs)
        return answer(self.replies.pop(0))


def lookup(name: str, version: str) -> list[str]:
    if name == "numpy" and version == "2.1.3":
        return [HASH, HASH2]
    raise LookupError(f"{name}=={version} is not on the package index")


def proposal(**overrides):
    value = {"name": "Late payers", "reason": "A logistic regression fits a yes-or-no outcome.",
             "manifest": MANIFEST, "source": SOURCE, "packages": []}
    value.update(overrides)
    return value


def test_a_draft_is_the_three_files_checked_and_never_written():
    client = Scripted(proposal())
    turn = md.methodology_draft_turn(
        {"message": "Predict which customers pay late", "context": {"target_kind": "binary"}},
        client, "gpt-5.5", lookup)
    assert turn["ok"], turn
    result = turn["result"]
    assert result["kind"] == "methodology_draft"
    assert [f["path"] for f in result["files"]] == ["methodology.json", "methodology.py",
                                                    "requirements.lock"]
    manifest = json.loads(result["files"][0]["contents"])
    assert manifest["interface"] == 1
    assert manifest["entrypoint"] == "methodology.py"
    assert manifest["packages"] == "requirements.lock"
    assert result["files"][2]["contents"] == "", "the standard library only: an empty lock"
    sent = client.seen[0]
    assert sent["response_format"] == {"type": "json_object"}
    assert "Its target's kind: binary" in sent["messages"][1]["content"]
    assert "Never write hashes" in sent["messages"][0]["content"]


def test_packages_are_pinned_with_every_wheels_hash_from_the_index():
    turn = md.methodology_draft_turn({"message": "segments"}, Scripted(
        proposal(packages=["numpy==2.1.3"])), "gpt-5.5", lookup)
    assert turn["ok"], turn
    lock = turn["result"]["files"][2]["contents"]
    assert "numpy==2.1.3 \\\n" in lock
    assert f"--hash=sha256:{HASH} \\\n" in lock
    assert lock.rstrip().endswith(f"--hash=sha256:{HASH2}")


def test_a_failing_draft_gets_one_round_with_its_findings_then_fails_with_them():
    broken = proposal(source="def fit(data, params):\n    return b''\n",
                      packages=["numpy>=2", "nope==1.0"])
    client = Scripted(broken, broken)
    turn = md.methodology_draft_turn({"message": "x"}, client, "gpt-5.5", lookup)
    assert not turn["ok"]
    assert turn["rounds"] == 2
    checks = {f["check"] for f in turn["findings"]}
    assert {"entrypoint.predict", "entrypoint.score", "packages"} <= checks
    retry = client.seen[1]["messages"][-1]["content"]
    assert "entrypoint.score" in retry and "not pinned" in retry
    assert "nope==1.0 is not on the package index" in turn["error"]


def test_the_second_round_can_repair_the_first():
    client = Scripted("not json", proposal())
    turn = md.methodology_draft_turn({"message": "x"}, client, "gpt-5.5", lookup)
    assert turn["ok"] and turn["rounds"] == 2


def test_the_manifest_is_checked_as_lake_reads_it():
    bad = dict(MANIFEST, metrics=[], inputs={"kinds": ["spreadsheet"],
                                             "target": {"required": False, "kind": "binary"}},
               parameters=[{"name": "k", "kind": "int", "default": 20, "minimum": 2,
                            "maximum": 10}])
    checks = {f.check for f in md.check_manifest(bad)}
    assert checks == {"manifest.metrics", "manifest.inputs.kinds",
                      "manifest.inputs.target.required", "manifest.parameters[0]"}
    assert md.check_manifest(MANIFEST) == []


def test_wheel_hashes_come_from_the_index_and_a_missing_pin_is_named():
    def index(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/pypi/numpy/2.1.3/json":
            return httpx.Response(200, json={"urls": [
                {"packagetype": "sdist", "digests": {"sha256": "c" * 64}},
                {"packagetype": "bdist_wheel", "digests": {"sha256": HASH2}},
                {"packagetype": "bdist_wheel", "digests": {"sha256": HASH}}]})
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(index))
    assert md.pypi_wheel_hashes("numpy", "2.1.3", client) == [HASH, HASH2]
    try:
        md.pypi_wheel_hashes("numpy", "0.0.1", client)
    except LookupError as error:
        assert "not on the package index" in str(error)
    else:
        raise AssertionError("a missing version is a LookupError")


def test_the_service_answers_a_methodology_draft_turn_and_keeps_nothing_on_disk(
        tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(md, "pypi_wheel_hashes", lookup)
    state = service.State()
    state.trace_dir = tmp_path
    state.lake_url = "http://lake"
    client = Scripted(proposal())
    result = service.run_turn({"kind": "methodology_draft", "message": "late payers",
                               "lake_token": "lat.task.secret", "lake_url": "http://lake",
                               "context": {"name": "Late payers"}}, state, client)
    assert result["ok"], result
    assert result["result"]["name"] == "Late payers"
    assert list(tmp_path.iterdir()) == [], "no trace file on the pod's disk (#44)"
    logged = [json.loads(line) for line in capsys.readouterr().out.splitlines()
              if result["trace_id"] in line]
    assert logged and logged[0]["kind"] == "methodology_draft"
    assert "lat.task.secret" not in json.dumps(logged)
    assert "late payers" not in json.dumps(logged), "what was asked stays off the log"

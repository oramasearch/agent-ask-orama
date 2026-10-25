"""agent-ask-orama#44 (LSR-076): nothing the shared service keeps grows without limit.

Conversations used to live in a dict that only grew, a turn that failed kept the person's message,
and every turn wrote a trace file to the pod's disk.
"""

from __future__ import annotations

import httpx
import pytest

from agent_ask_orama import agent, service
from agent_ask_orama.conversations import Conversations, message_bytes, trim
from test_agent import FakeLake, Scripted, message, turn


def system() -> dict:
    return {"role": "system", "content": "prompt"}


def one_turn(n: int, size: int = 10) -> list[dict]:
    """A person's message, a tool call and its answer, then the reply: one whole turn."""
    return [{"role": "user", "content": f"q{n}" + "x" * size},
            {"role": "assistant", "content": "", "tool_calls": [{"id": f"c{n}"}]},
            {"role": "tool", "tool_call_id": f"c{n}", "content": "r" * size},
            {"role": "assistant", "content": f"a{n}"}]


def conversation(turns: int, size: int = 10) -> list[dict]:
    history = [system()]
    for n in range(turns):
        history += one_turn(n, size)
    return history


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_the_oldest_whole_turns_go_first_and_the_system_message_stays():
    history = conversation(5)
    trim(history, max_turns=2, max_bytes=10**9)
    assert history == [system()] + one_turn(3) + one_turn(4)


def test_a_conversation_is_cut_to_its_byte_budget_by_whole_turns():
    history = conversation(6, size=1000)
    budget = sum(message_bytes(m) for m in [system()] + one_turn(0, 1000) * 2)
    trim(history, max_turns=100, max_bytes=budget)
    assert history == [system()] + one_turn(4, 1000) + one_turn(5, 1000)
    tool_ids = [m["tool_call_id"] for m in history if m["role"] == "tool"]
    assert tool_ids == ["c4", "c5"], "a tool answer never loses its call"


def test_a_single_turn_over_the_budget_leaves_only_the_system_message():
    history = conversation(1, size=5000)
    trim(history, max_turns=100, max_bytes=1000)
    assert history == [system()]


def test_the_least_recently_used_conversation_is_dropped_past_the_count():
    memory = Conversations(max_conversations=3)
    for key in "abc":
        memory[key] = conversation(1)
    memory["a"]  # used: b is now the oldest
    memory["d"] = conversation(1)
    assert sorted(memory) == ["a", "c", "d"]


def test_conversations_are_dropped_past_the_total_bytes():
    one = sum(message_bytes(m) for m in conversation(1, 1000))
    memory = Conversations(max_total_bytes=3 * one)
    for key in "abcde":
        memory[key] = conversation(1, 1000)
    assert sorted(memory) == ["c", "d", "e"]
    assert memory.total_bytes() <= 3 * one


def test_growth_after_a_conversation_was_handed_out_is_counted():
    one = sum(message_bytes(m) for m in conversation(1, 1000))
    memory = Conversations(max_total_bytes=3 * one, max_turns=100)
    memory["a"] = conversation(1, 1000)
    memory["a"].extend(one_turn(1, 1000) + one_turn(2, 1000))  # a turn appends in place
    memory["b"] = conversation(1, 1000)
    assert "a" not in memory, "a grew to three turns; with b it is over the total"


def test_an_idle_conversation_expires():
    clock = Clock()
    memory = Conversations(idle_seconds=60, clock=clock)
    memory["old"] = conversation(1)
    clock.now += 30
    memory["new"] = conversation(1)
    clock.now += 31
    assert "old" not in memory and "new" in memory
    clock.now += 60
    assert len(memory) == 0


def test_setdefault_and_moving_a_conversation_to_a_new_key_work():
    """The mapping is used as a dict is: `setdefault` (by id), or popped and stored again under a
    new key (agent-ask-orama#42 keys a conversation by the task that last continued it)."""
    memory = Conversations(max_turns=2)
    history = memory.setdefault("t1", [])
    history += conversation(3)
    moved = memory.pop("t1", [])
    memory["t2"] = moved
    assert "t1" not in memory and memory["t2"] is moved
    assert moved == [system()] + one_turn(1) + one_turn(2), "trimmed when stored"


def test_the_limits_come_from_the_environment(monkeypatch):
    monkeypatch.setenv("ASK_ORAMA_CONVERSATIONS", "7")
    monkeypatch.setenv("ASK_ORAMA_CONVERSATION_TURNS", "3")
    monkeypatch.setenv("ASK_ORAMA_CONVERSATION_BYTES", "4096")
    monkeypatch.setenv("ASK_ORAMA_CONVERSATIONS_BYTES", "65536")
    monkeypatch.setenv("ASK_ORAMA_CONVERSATION_IDLE_SECONDS", "120")
    memory = Conversations.from_env()
    assert (memory.max_conversations, memory.max_turns, memory.max_bytes,
            memory.max_total_bytes, memory.idle_seconds) == (7, 3, 4096, 65536, 120)
    monkeypatch.setenv("ASK_ORAMA_CONVERSATIONS", "-1")
    monkeypatch.setenv("ASK_ORAMA_CONVERSATION_TURNS", "lots")
    memory = Conversations.from_env()
    assert memory.max_conversations == 256 and memory.max_turns == 20


def service_turn(state, body, client, task=None, prior=None):
    """One turn as Lake's bus delivers it: a claim names the account, workspace and task, and
    `prior_turn` the task it follows (#46 keys a conversation by that task, never by a named id)."""
    if prior:
        body = {**body, "prior_turn": {"task_id": prior}}
    claim = {"customer_id": "c-1", "workspace_id": "w-1", "task_id": task} if task else None
    return service.run_turn(body, state, client,
                            agent.Lake(turn(), transport=httpx.MockTransport(FakeLake())), claim)


def lake_state():
    state = service.State()
    state.lake_url = "http://lake"  # the service's own LAKE_URL (#40)
    return state


def key(task):
    return ("c-1", "w-1", task)


def test_many_conversations_keep_the_service_within_its_limit(monkeypatch):
    monkeypatch.setenv("ASK_ORAMA_CONVERSATIONS", "5")
    state = lake_state()
    for n in range(40):
        result = service_turn(state, {"message": f"hi {n}", "lake_token": "person-key"},
                              Scripted(message(content="Hello.")), task=f"t{n}")
        assert result["ok"], result
    assert len(state.conversations) == 5
    assert sorted(state.conversations) == sorted(key(f"t{n}") for n in range(35, 40))


def test_one_long_conversation_keeps_only_its_last_turns(monkeypatch):
    monkeypatch.setenv("ASK_ORAMA_CONVERSATION_TURNS", "3")
    state = lake_state()
    body = {"lake_token": "person-key"}
    for n in range(10):
        service_turn(state, {**body, "message": f"turn {n}"}, Scripted(message(content="ok")),
                     task=f"t{n}", prior=f"t{n - 1}" if n else None)
    history = state.conversations[key("t9")]
    people = [m["content"] for m in history if m["role"] == "user"]
    assert len(people) == 3 and people[0].startswith("turn 7"), people
    assert history[0]["role"] == "system"


class Failing:
    def __init__(self) -> None:
        self.chat = type("Chat", (), {"completions": self})()

    def create(self, **_):
        raise RuntimeError("model unavailable")


def test_a_turn_that_fails_leaves_nothing_in_the_conversation():
    state = lake_state()
    body = {"message": "a very long question " * 1000, "lake_token": "person-key"}
    with pytest.raises(RuntimeError):
        service_turn(state, body, Failing(), task="t1")
    assert not state.conversations.get(key("t1")), "the failed turn's message is not kept"
    service_turn(state, {**body, "message": "hi"}, Scripted(message(content="Hello.")), task="t2")
    with pytest.raises(RuntimeError):
        service_turn(state, body, Failing(), task="t3", prior="t2")
    kept = state.conversations[key("t3")]
    assert [m["role"] for m in kept] == ["system", "user", "assistant"]
    assert kept[1]["content"].startswith("hi")


def test_a_turn_writes_nothing_to_the_pods_disk(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TRACE_DIR", str(tmp_path))
    state = lake_state()
    state.trace_dir = tmp_path  # where the service used to write; it must not now
    result = service_turn(state, {"message": "secret question", "lake_token": "person-key",
                                  "lake_url": "http://lake", "conversation_id": "conv"},
                          Scripted(message(content="secret answer")))
    assert result["ok"] and result["trace_id"]
    assert list(tmp_path.iterdir()) == []
    logged = capsys.readouterr().out
    assert result["trace_id"] in logged, "the trace id is still logged, to find the turn"
    for said in ("secret question", "secret answer", "person-key"):
        assert said not in logged

"""Ask Orama: the general agent for all of lake (lake#228, zetta#1018).

It works as the signed-in person and never more: every call carries the key lake delegates to it
for this turn, derived from the person's session, so lake's policy decides what it may read. It
**reads** directly, **proposes** every change for the person to confirm in lake (it never holds the
authority to write), and **delegates** to any agent the person can see: the Agent Library's
specialized agents and every user-created one, through lake.

Its tools are few and generic because lake has hundreds of capabilities, far more than a model can
be handed as separate tools. What makes them safe to be generic is that the vocabulary is derived:
the index of capabilities it may name comes from lake's own OpenAPI at every turn, so it cannot
name one that does not exist, and lake refuses anything the person may not do.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
from openai import OpenAI

PROMPT_VERSION = "v2"
PROMPTS = Path(__file__).parent / "prompts"
MAX_ROUNDS = 10

# Never offered, whatever the OpenAPI lists: signing in, recovering accounts and minting
# credentials are ceremonies a person performs, not something an agent proposes.
EXCLUDED_PREFIXES = ("sign_in", "sign_up", "begin_", "complete_", "recover", "verify_mfa",
                     "enroll_mfa", "register_passkey", "start_oauth", "start_sso", "exchange_",
                     "issue_", "mint_", "rotate_identity", "decrypt", "read_secret")


@dataclass
class Capability:
    name: str
    read: bool
    summary: str
    # Whether lake's input for it has a customer_id (a query parameter or a body property).
    takes_customer: bool = True
    # The inputs it requires besides the space: what a request must name, or Ask Orama find.
    required: frozenset[str] = frozenset()
    # How it is sent. A POST can still only read (workspace_query): `read` says what it does.
    get: bool = True


@dataclass
class Turn:
    """One message from the person, with what lake hands over for it."""

    message: str
    lake_url: str
    lake_token: str
    customer_id: str = ""
    page: dict[str, Any] = field(default_factory=dict)
    conversation_id: str = ""


@dataclass
class Answer:
    reply: str = ""
    reads: list[dict[str, Any]] = field(default_factory=list)
    proposals: list[dict[str, Any]] = field(default_factory=list)
    delegations: list[dict[str, Any]] = field(default_factory=list)
    rounds: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {"reply": self.reply, "reads": self.reads, "proposals": self.proposals,
                "delegations": self.delegations, "rounds": self.rounds}


def capability_index(openapi: dict[str, Any]) -> dict[str, Capability]:
    """Every capability lake serves, read or write, from its OpenAPI."""
    index: dict[str, Capability] = {}
    for path, operations in (openapi.get("paths") or {}).items():
        if not path.startswith("/v1/") or path.count("/") != 2:
            continue
        name = path.removeprefix("/v1/")
        if name.startswith(EXCLUDED_PREFIXES):
            continue
        for method, operation in operations.items():
            if method not in {"get", "post"}:
                continue
            summary = (operation.get("summary") or operation.get("description") or "").strip()
            # What it does is lake's x-lake-action (read | write); the method only says how to
            # send it. Without the extension (an older lake), a GET is a read.
            action = operation.get("x-lake-action")
            read = action == "read" if action else method == "get"
            index[name] = Capability(name, read, summary.split("\n")[0][:140],
                                     "customer_id" in input_fields(operation),
                                     frozenset(required_fields(operation) - {"customer_id"}),
                                     get=method == "get")
    return index


def input_fields(operation: dict[str, Any]) -> set[str]:
    """The names a capability's input accepts: its query parameters or its JSON body's properties."""
    fields = {parameter.get("name", "") for parameter in operation.get("parameters") or []}
    schema = (((operation.get("requestBody") or {}).get("content") or {})
              .get("application/json") or {}).get("schema") or {}
    return fields | set((schema.get("properties") or {}).keys())


def required_fields(operation: dict[str, Any]) -> set[str]:
    """The names a capability's input requires."""
    fields = {parameter.get("name", "") for parameter in operation.get("parameters") or []
              if parameter.get("required")}
    schema = (((operation.get("requestBody") or {}).get("content") or {})
              .get("application/json") or {}).get("schema") or {}
    return fields | set(schema.get("required") or [])


def index_text(index: dict[str, Capability]) -> str:
    reads = [f"- {c.name}: {c.summary}" for c in index.values() if c.read]
    writes = [f"- {c.name}: {c.summary}" for c in index.values() if not c.read]
    return ("\n\n## Reads you may call with lake_read\n" + "\n".join(sorted(reads))
            + "\n\n## Changes you may only propose with lake_propose\n" + "\n".join(sorted(writes)))


TOOLS = [
    {"type": "function", "function": {
        "name": "lake_read",
        "description": "Call one of lake's reads as the person. Workspace (Zetta) reads go through "
                       "workspace_query with {capability, input}.",
        "parameters": {"type": "object", "properties": {
            "capability": {"type": "string"}, "input": {"type": "object"}},
            "required": ["capability"]}}},
    {"type": "function", "function": {
        "name": "lake_propose",
        "description": "Propose a change for the person to confirm in lake. Nothing happens until "
                       "they confirm. Say what it will change in `impact`.",
        "parameters": {"type": "object", "properties": {
            "capability": {"type": "string"}, "input": {"type": "object"},
            "impact": {"type": "string"}}, "required": ["capability", "input", "impact"]}}},
    {"type": "function", "function": {
        "name": "delegate",
        "description": "Hand a request to another agent and get its answer: a specialized agent of "
                       "the Agent Library by key (agent-project builds and changes Pipelines, "
                       "agent-autosuggest recommends Opportunities from a profile) or any agent "
                       "the person built, by its id from list_agents. An agent that only runs "
                       "unattended is started by proposing launch_agent instead.",
        "parameters": {"type": "object", "properties": {
            "agent": {"type": "string"}, "request": {"type": "string"},
            "context": {"type": "object"}}, "required": ["agent", "request"]}}},
]


class Lake:
    """lake, as the person, for one turn."""

    def __init__(self, turn: Turn, transport: httpx.BaseTransport | None = None) -> None:
        self.turn = turn
        self.client = httpx.Client(base_url=turn.lake_url.rstrip("/"), timeout=180.0,
                                   headers={"Authorization": f"Bearer {turn.lake_token}"},
                                   transport=transport)

    def close(self) -> None:
        self.client.close()

    def openapi(self) -> dict[str, Any]:
        response = self.client.get("/v1/openapi.json")
        response.raise_for_status()
        return response.json()

    def call(self, capability: str, arguments: dict[str, Any], read: bool) -> dict[str, Any]:
        try:
            if read:
                params = {k: v if isinstance(v, str) else json.dumps(v)
                          for k, v in arguments.items() if v is not None}
                response = self.client.get(f"/v1/{capability}", params=params)
            else:
                response = self.client.post(f"/v1/{capability}", json=arguments)
            body = response.json()
        except (httpx.HTTPError, ValueError) as error:
            return {"ok": False, "error": {"message": f"{type(error).__name__}: {error}"}}
        return body if isinstance(body, dict) else {"ok": False, "error": {"message": "no JSON"}}


def with_customer(capability: Capability | None, arguments: dict[str, Any],
                  customer_id: str) -> dict[str, Any]:
    """The space the person is working in, unless the call names another or takes no space."""
    if capability is not None and not capability.takes_customer:
        return arguments
    if customer_id and "customer_id" not in arguments:
        return {**arguments, "customer_id": customer_id}
    return arguments


def observation(body: dict[str, Any]) -> str:
    if body.get("ok"):
        return json.dumps(body.get("value"), default=str)[:20000]
    error = body.get("error") or {}
    return f"FAILED: {error.get('code', '')} {error.get('message', '')}".strip()


def answer_turn(turn: Turn, history: list[dict[str, Any]], client: OpenAI, model: str,
                lake: Lake | None = None) -> Answer:
    """Continue the conversation in `history` (system first when non-empty) by one turn."""
    owned = lake is None
    lake = lake or Lake(turn)
    answer = Answer()
    try:
        index = capability_index(lake.openapi())
        if not history:
            history.append({"role": "system", "content":
                            (PROMPTS / f"{PROMPT_VERSION}.md").read_text() + index_text(index)})
        page = f"\n\n(The person is on {json.dumps(turn.page)})" if turn.page else ""
        history.append({"role": "user", "content": turn.message + page})
        for round_number in range(1, MAX_ROUNDS + 1):
            answer.rounds = round_number
            message = client.chat.completions.create(model=model, messages=history,
                                                     tools=TOOLS).choices[0].message
            history.append(message.model_dump(exclude_none=True))
            if not message.tool_calls:
                answer.reply = message.content or ""
                return answer
            for call in message.tool_calls:
                try:
                    arguments = json.loads(call.function.arguments or "{}")
                except json.JSONDecodeError:
                    arguments = {}
                content = handle(call.function.name, arguments, index, turn, lake, answer)
                history.append({"role": "tool", "tool_call_id": call.id, "content": content})
        answer.reply = "I stopped before finishing: this turn reached its limit of tool rounds."
        return answer
    finally:
        if owned:
            lake.close()


FOLLOW_SECONDS = 240.0


def follow(lake: Lake, customer_id: str, task_id: str, budget: float = FOLLOW_SECONDS,
           clock=time.monotonic) -> dict[str, Any]:
    """A delegated task, followed with receive_agent_events until it finishes or the budget ends.

    Answers the envelope with the task as it stands: finished, with the subagent's answer, or still
    working (then the person is told it is, and where to follow it).
    """
    deadline = clock() + budget
    sequence = 1
    while True:
        body = lake.call("receive_agent_events", {"customer_id": customer_id, "task_id": task_id,
                                                  "from_sequence": sequence, "wait_ms": 10000},
                         read=True)
        if not body.get("ok"):
            return body
        value = body.get("value") or {}
        sequence = int(value.get("next_sequence") or sequence)
        task = value.get("task") or {}
        if task.get("status") in ("succeeded", "failed") or clock() >= deadline:
            return {"ok": True, "value": task}


def handle(name: str, arguments: dict[str, Any], index: dict[str, Capability], turn: Turn,
           lake: Lake, answer: Answer) -> str:
    """One tool call. Reads run; proposals are recorded, never run; delegation goes through lake."""
    if name == "delegate":
        agent, request = arguments.get("agent", ""), arguments.get("request", "")
        body = lake.call("agent_turn", {"customer_id": turn.customer_id, "agent": agent,
                                        "message": request,
                                        "context": arguments.get("context") or {}}, read=False)
        task_id = (body.get("value") or {}).get("task_id") if body.get("ok") else None
        if task_id:
            # A library agent answers on lake's agent bus (lake#269): follow its task.
            body = follow(lake, turn.customer_id, task_id)
        answer.delegations.append({"agent": agent, "request": request, "ok": bool(body.get("ok")),
                                   "answer": body.get("value") if body.get("ok") else None,
                                   "error": (body.get("error") or {}).get("message")})
        return observation(body)
    capability = index.get(arguments.get("capability", ""))
    if capability is None:
        return (f"FAILED: '{arguments.get('capability')}' is not a lake capability. Use a name "
                "from the lists in your instructions.")
    payload = with_customer(capability, arguments.get("input") or {}, turn.customer_id)
    if name == "lake_read":
        if not capability.read:
            return (f"FAILED: {capability.name} changes something; propose it with lake_propose "
                    "so the person can confirm it.")
        body = lake.call(capability.name, payload, read=capability.get)
        answer.reads.append({"capability": capability.name, "input": payload,
                             "ok": bool(body.get("ok"))})
        return observation(body)
    if name == "lake_propose":
        if capability.read:
            return f"{capability.name} only reads; call it with lake_read instead."
        proposal = {"capability": capability.name, "input": payload,
                    "impact": arguments.get("impact", "")}
        answer.proposals.append(proposal)
        return ("PROPOSED, NOT DONE. The person sees this and confirms it in lake. Tell them "
                "what it will do; do not say it is done.")
    return f"FAILED: '{name}' is not one of your tools."

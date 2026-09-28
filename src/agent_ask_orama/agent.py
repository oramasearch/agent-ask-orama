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

PROMPT_VERSION = "v7"
PROMPTS = Path(__file__).parent / "prompts"
MAX_ROUNDS = 10
OLD_ENGINE_ISSUE = "zetta#1061"
APPLICATION_AGENT = "agent-application"

SOLUTION_READ_CAPABILITIES = frozenset({
    "get_solution",
    "get_policy",
    "get_experiment",
    "list_ledger",
    "get_monitor",
    "get_roi_readout",
})
SOLUTION_ACTION_CAPABILITIES = frozenset({
    "create_solution",
    "run_solution",
    "create_policy",
    "update_policy",
    "decide",
    "approve_decision",
})

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


@dataclass
class MethodologyCatalog:
    """The methodology registry observed during this turn."""

    methodologies: dict[str, dict[str, Any]] = field(default_factory=dict)
    loaded: bool = False
    old_engine: bool = False

    def observe(self, payload: dict[str, Any], body: dict[str, Any]) -> bool:
        """Record a list_methodologies result and return whether this was that read."""
        if payload.get("capability") != "list_methodologies":
            return False
        error = body.get("error") or {}
        if not body.get("ok") and error.get("code") == "unknown_capability":
            self.methodologies = {
                "M-1": {
                    "id": "M-1",
                    "name": "Churn / GBDT classification",
                    "runnable": True,
                    "partial": False,
                    "issue": None,
                }
            }
            self.loaded = True
            self.old_engine = True
            return True
        value = body.get("value") or {}
        items = value.get("methodologies") if isinstance(value, dict) else None
        if body.get("ok") and isinstance(items, list):
            self.methodologies = {
                item["id"]: item
                for item in items
                if isinstance(item, dict) and isinstance(item.get("id"), str)
            }
            self.loaded = True
            self.old_engine = False
        return True

    def fallback_observation(self) -> str:
        return json.dumps({
            "methodologies": list(self.methodologies.values()),
            "compatibility": (
                "This workspace engine predates list_methodologies. Only M-1 runs; "
                f"registry support is tracked by {OLD_ENGINE_ISSUE}."
            ),
        })

    def refusal(self, methodology: str) -> str | None:
        """Explain why a named methodology cannot be proposed, or allow it."""
        if not self.loaded:
            return (
                "FAILED: methodology_registry_required Read workspace_query "
                "list_methodologies at the start of this turn before proposing a methodology."
            )
        item = self.methodologies.get(methodology)
        if item is not None and item.get("runnable"):
            return None
        if self.old_engine:
            return unsupported(methodology, "this workspace engine only runs M-1",
                               OLD_ENGINE_ISSUE)
        if item is None:
            runnable = sorted(key for key, value in self.methodologies.items()
                              if value.get("runnable"))
            return (f"FAILED: not_supported {methodology} is not in this engine's methodology "
                    f"registry. Runnable methodologies: {', '.join(runnable) or 'none'}.")
        name = str(item.get("name") or methodology)
        issue = str(item.get("issue") or "")
        return unsupported(methodology, name, issue)


@dataclass
class SolutionCatalog:
    """The solution registry observed during this turn."""

    solutions: dict[str, dict[str, Any]] = field(default_factory=dict)
    loaded: bool = False
    old_engine: bool = False

    def observe(self, payload: dict[str, Any], body: dict[str, Any]) -> bool:
        """Record a list_solutions result and return whether this was that read."""
        if payload.get("capability") != "list_solutions":
            return False
        error = body.get("error") or {}
        if not body.get("ok") and error.get("code") == "unknown_capability":
            self.solutions = {}
            self.loaded = True
            self.old_engine = True
            return True
        value = body.get("value") or {}
        items = value.get("solutions") if isinstance(value, dict) else None
        if body.get("ok") and isinstance(items, list):
            self.solutions = {
                item["id"]: item
                for item in items
                if isinstance(item, dict) and isinstance(item.get("id"), str)
            }
            self.loaded = True
            self.old_engine = False
        return True

    def fallback_observation(self) -> str:
        return json.dumps({
            "solutions": [],
            "compatibility": (
                "This workspace engine predates list_solutions. Solution catalogue, policy, "
                "ledger, monitor, and measured readout operations are not deployed yet. "
                "Methodology support may still be available through list_methodologies."
            ),
        })

    def refusal(self, solution: str, level: Any) -> str | None:
        """Explain why a solution creation proposal is invalid, or allow it."""
        required = self.required()
        if required:
            return required
        item = self.solutions.get(solution)
        if item is None:
            return f"FAILED: not_supported {solution} is not in this engine's solution registry."
        if item.get("status") == "sketch":
            name = str(item.get("name") or solution)
            condition = str(item.get("promotion_condition") or "its promotion condition")
            issue = str(item.get("issue") or "")
            return solution_unsupported(solution, name, condition, issue)
        levels = item.get("levels") or item.get("capability_levels") or []
        declared = {
            entry.get("level") if isinstance(entry, dict) else entry
            for entry in levels
        }
        if level not in declared:
            available = ", ".join(str(value) for value in sorted(
                value for value in declared if isinstance(value, int)
            ))
            return (
                f"FAILED: not_supported level {level} is not declared for {solution}. "
                f"Available levels: {available or 'none'}."
            )
        return None

    def required(self) -> str | None:
        """Require this turn's registry before a solution operation."""
        if not self.loaded:
            return (
                "FAILED: solution_registry_required Read workspace_query list_solutions at the "
                "start of this turn before a solution operation."
            )
        if self.old_engine:
            return (
                "FAILED: not_supported This workspace engine has no solution registry. "
                "Solution operations are not deployed yet; use methodologies only."
            )
        return None


def issue_url(issue: str) -> str:
    if issue.startswith("zetta#") and issue.removeprefix("zetta#").isdigit():
        return "https://github.com/oramasearch/zetta/issues/" + issue.removeprefix("zetta#")
    return ""


def unsupported(methodology: str, name: str, issue: str) -> str:
    issue_text = f"; tracked by {issue}"
    url = issue_url(issue)
    if url:
        issue_text += f" ({url})"
    if not issue:
        issue_text = ""
    return f"FAILED: not_supported {name} ({methodology}) is not supported yet{issue_text}."


def solution_unsupported(solution: str, name: str, condition: str, issue: str) -> str:
    issue_text = f" Tracked by {issue}." if issue else ""
    url = issue_url(issue)
    if url:
        issue_text = f" Tracked by {issue} ({url})."
    return (
        f"FAILED: not_supported {name} ({solution}) is a sketch and cannot be created. "
        f"Promotion condition: {condition}.{issue_text}"
    )


def solution_creation(payload: dict[str, Any]) -> tuple[str, Any] | None:
    """Return a nested create_solution request's identifier and level."""
    if payload.get("capability") != "create_solution":
        return None
    arguments = payload.get("input") or {}
    if not isinstance(arguments, dict):
        return None
    solution = arguments.get("solution")
    if not isinstance(solution, str) or not solution:
        return None
    return solution, arguments.get("level")


def named_methodologies(value: Any) -> list[str]:
    """Find methodology identifiers in a proposed nested input."""
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "methodology" and isinstance(item, str) and item:
                found.append(item)
            else:
                found.extend(named_methodologies(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(named_methodologies(item))
    return found


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
                       "agent-autosuggest recommends Opportunities from a profile, and "
                       "agent-application builds and changes Apps) or any agent the person built, "
                       "by its id from list_agents. ApplicationAgent turns are sent to lake with "
                       "kind app. An agent that only runs unattended is started by proposing "
                       "launch_agent instead.",
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
    methodologies = MethodologyCatalog()
    solutions = SolutionCatalog()
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
                content = handle(call.function.name, arguments, index, turn, lake, answer,
                                 methodologies, solutions)
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
           lake: Lake, answer: Answer, methodologies: MethodologyCatalog,
           solutions: SolutionCatalog) -> str:
    """One tool call. Reads run; proposals are recorded, never run; delegation goes through lake."""
    if name == "delegate":
        agent, request = arguments.get("agent", ""), arguments.get("request", "")
        kind = "app" if agent == APPLICATION_AGENT else None
        payload = {
            "customer_id": turn.customer_id,
            "agent": agent,
            "message": request,
            "context": arguments.get("context") or {},
        }
        if kind is not None:
            payload["kind"] = kind
        body = lake.call("agent_turn", payload, read=False)
        task_id = (body.get("value") or {}).get("task_id") if body.get("ok") else None
        if task_id:
            # A library agent answers on lake's agent bus (lake#269): follow its task.
            body = follow(lake, turn.customer_id, task_id)
        answer.delegations.append({"agent": agent, "kind": kind, "request": request,
                                   "ok": bool(body.get("ok")),
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
        workspace_operation = (
            payload.get("capability")
            if capability.name == "workspace_query"
            else None
        )
        if workspace_operation in SOLUTION_READ_CAPABILITIES:
            refusal = solutions.required()
            if refusal:
                return refusal
        body = lake.call(capability.name, payload, read=capability.get)
        answer.reads.append({"capability": capability.name, "input": payload,
                             "ok": bool(body.get("ok"))})
        methodology_read = capability.name == "workspace_query" and methodologies.observe(
            payload, body)
        if methodology_read and methodologies.old_engine:
            return methodologies.fallback_observation()
        solution_read = capability.name == "workspace_query" and solutions.observe(payload, body)
        if solution_read and solutions.old_engine:
            return solutions.fallback_observation()
        return observation(body)
    if name == "lake_propose":
        if capability.read:
            return f"{capability.name} only reads; call it with lake_read instead."
        workspace_operation = (
            payload.get("capability")
            if capability.name == "workspace_act"
            else None
        )
        if workspace_operation in SOLUTION_ACTION_CAPABILITIES:
            refusal = solutions.required()
            if refusal:
                return refusal
        for methodology in named_methodologies(payload):
            refusal = methodologies.refusal(methodology)
            if refusal:
                return refusal
        creation = solution_creation(payload)
        if creation is not None:
            refusal = solutions.refusal(*creation)
            if refusal:
                return refusal
        proposal = {"capability": capability.name, "input": payload,
                    "impact": arguments.get("impact", "")}
        answer.proposals.append(proposal)
        return ("PROPOSED, NOT DONE. The person sees this and confirms it in lake. Tell them "
                "what it will do; do not say it is done.")
    return f"FAILED: '{name}' is not one of your tools."

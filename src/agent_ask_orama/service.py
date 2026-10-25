"""Ask Orama as the lake-wide service (zetta#1018): `POST /v1/turn`, `GET /healthz`.

lake calls it for every message in the Ask Orama panel, passing the person's delegated key for the
turn (`lake_token`), the account, and the page they are on. The same key reaches the model through
lake's model gateway (`model.py`). Conversations are kept in memory under the Lake task that last
continued them (`State.history`), never by the conversation id a turn names.
Standard library only.
"""

from __future__ import annotations

import hmac
import json
import os
from importlib.metadata import PackageNotFoundError, version
import threading
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from openai import OpenAI

from agent_ask_orama import lake_bus
from agent_ask_orama.agent import PROMPT_VERSION, Turn, answer_turn, proposal_states
from agent_ask_orama.methodology_draft import methodology_draft_turn
from agent_ask_orama.model import gateway_client


class State:
    def __init__(self) -> None:
        self.model = os.environ.get("ASK_ORAMA_MODEL", "gpt-5.5")
        self.token = os.environ.get("AGENT_SERVICE_TOKEN", "")
        self.lake_url = os.environ.get("LAKE_URL", "")
        self.trace_dir = Path(os.environ.get("TRACE_DIR", "/tmp/agent-ask-orama-traces"))
        self.lock = threading.Lock()
        # (customer_id, workspace_id, task_id) -> the conversation that task last continued.
        self.conversations: dict[tuple[str, str, str], list[dict[str, Any]]] = {}

    def history(self, claim: object, prior_task_id: str) -> list[dict[str, Any]]:
        """The conversation a turn continues, now kept under the turn's own task.

        A turn continues only the conversation its prior turn left in the same account and
        workspace. Both come from Lake: `claim` is the claim reply's task, account and workspace
        (`lake_bus.turn_body`), and the prior turn is the body's `prior_turn`, which Lake attaches
        only for the person who asked it. Any other turn, including a direct `/v1/turn` call with
        no claim, starts a new conversation. The conversation id a turn names is never the key:
        anyone can name one (agent-ask-orama#42).
        """
        owner = claimed_task(claim)
        if owner is None:
            return []
        account, workspace, _ = owner
        with self.lock:
            # Every kept key has a task id, so a turn with no prior turn finds nothing.
            history = self.conversations.pop((account, workspace, prior_task_id), [])
            self.conversations[owner] = history
            return history


def claimed_task(claim: object) -> tuple[str, str, str] | None:
    """`(customer_id, workspace_id, task_id)` from a turn's claim, or None unless all three are
    non-empty strings."""
    if not isinstance(claim, dict):
        return None
    owner = claim.get("customer_id"), claim.get("workspace_id"), claim.get("task_id")
    if not all(isinstance(part, str) and part for part in owner):
        return None
    return owner


def prior_task_id(body: dict[str, Any]) -> str:
    """The task id of the turn Lake says this one follows (`prior_turn`), or ""."""
    prior = body.get("prior_turn")
    task_id = prior.get("task_id") if isinstance(prior, dict) else None
    return task_id if isinstance(task_id, str) else ""


def package_version() -> str:
    """This agent's release, from the installed package (pyproject.toml's version)."""
    try:
        return version("agent-ask-orama")
    except PackageNotFoundError:
        return "unknown"


def health(state: State) -> dict[str, Any]:
    """`GET /healthz`: the agent, its release, the model and the prompt version."""
    return {"ok": True, "agent": "agent-ask-orama", "version": package_version(),
            "model": state.model, "prompt_version": PROMPT_VERSION}


def run_turn(body: dict[str, Any], state: State, client: OpenAI | None = None,
             lake=None, claim: object = None) -> dict[str, Any]:
    """One turn. `claim` is what Lake's claim reply said of the task (bus turns only); without
    it the turn keeps no conversation."""
    message = body.get("message") or ""
    token = body.get("lake_token") or ""
    lake_url = body.get("lake_url") or state.lake_url
    if not message or not token or not lake_url:
        return {"ok": False, "error": "a turn needs a message, the person's lake_token and lake"}
    conversation = body.get("conversation_id") or str(uuid.uuid4())
    if body.get("kind") == "methodology_draft":
        return run_methodology_draft(body, state, conversation, token, lake_url, client)
    turn = Turn(message=message, lake_url=lake_url, lake_token=token,
                customer_id=body.get("customer_id") or "", page=body.get("page") or {},
                conversation_id=conversation,
                # What became of the conversation's earlier proposals (lake#1194).
                proposal_states=proposal_states(body.get("context")))
    # The model is reached through lake with the turn's own key, which counts its tokens in the
    # turn's workspace (lake#248); this agent holds no provider key.
    model = client or gateway_client(lake_url, token)
    answer = answer_turn(turn, state.history(claim, prior_task_id(body)), model, state.model,
                         lake)
    trace_id = str(uuid.uuid4())
    state.trace_dir.mkdir(parents=True, exist_ok=True)
    (state.trace_dir / f"{trace_id}.json").write_text(json.dumps(
        {"trace_id": trace_id, "agent": "agent-ask-orama", "prompt_version": PROMPT_VERSION,
         "at": datetime.now(timezone.utc).isoformat(), "conversation_id": conversation,
         "message": message, "page": turn.page, "answer": answer.as_dict()}, indent=1,
        default=str))
    if answer.incomplete:
        # Out of tool rounds (agent-ask-orama#14): a partial answer is not a success. On lake's
        # bus this publishes `failed` with the partial answer as its message.
        return {"ok": False, "error": answer.reply, "conversation_id": conversation,
                "trace_id": trace_id, **answer.as_dict()}
    return {"ok": True, "conversation_id": conversation, "trace_id": trace_id, **answer.as_dict()}


def run_methodology_draft(body: dict[str, Any], state: State, conversation: str, token: str,
                          lake_url: str, client: OpenAI | None = None) -> dict[str, Any]:
    """Lake's New Methodology drawer asks for a first draft (lake#688): the three files of a
    methodology, checked, for the person to review. Nothing is written."""
    model = client or gateway_client(lake_url, token)
    answer = methodology_draft_turn(body, model, state.model)
    trace_id = str(uuid.uuid4())
    state.trace_dir.mkdir(parents=True, exist_ok=True)
    (state.trace_dir / f"{trace_id}.json").write_text(json.dumps(
        {"trace_id": trace_id, "agent": "agent-ask-orama", "kind": "methodology_draft",
         "at": datetime.now(timezone.utc).isoformat(), "conversation_id": conversation,
         "message": body.get("message") or "", "context": body.get("context") or {},
         "answer": answer}, indent=1, default=str))
    return {**answer, "conversation_id": conversation, "trace_id": trace_id}


def turn_refusal(authorization: str | None, token: str) -> tuple[int, str] | None:
    """Why `POST /v1/turn` is refused, as `(status, error)`, or None when the caller may proceed.

    The route fails closed: with `AGENT_SERVICE_TOKEN` unset or empty every turn is refused, so a
    service started without it is never open. The bearer is compared in constant time
    (`hmac.compare_digest` over bytes), so the comparison's timing says nothing about the token.
    """
    if not token:
        return 503, "AGENT_SERVICE_TOKEN is not set; this service refuses every turn"
    expected = f"Bearer {token}".encode()
    supplied = (authorization or "").encode("utf-8", "surrogateescape")
    if not hmac.compare_digest(supplied, expected):
        return 401, "unauthorized"
    return None


def serve() -> int:
    state = State()

    class Handler(BaseHTTPRequestHandler):
        def _send(self, status: int, body: dict[str, Any]) -> None:
            payload = json.dumps(body, default=str).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self) -> None:  # noqa: N802 (the stdlib's name)
            if self.path == "/healthz":
                self._send(200, health(state))
                return
            self._send(404, {"ok": False, "error": "not found"})

        def do_POST(self) -> None:  # noqa: N802
            if self.path != "/v1/turn":
                self._send(404, {"ok": False, "error": "not found"})
                return
            refusal = turn_refusal(self.headers.get("Authorization"), state.token)
            if refusal is not None:
                status, error = refusal
                self._send(status, {"ok": False, "error": error})
                return
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
            except (json.JSONDecodeError, ValueError):
                self._send(400, {"ok": False, "error": "the body is not JSON"})
                return
            try:
                answer = run_turn(body if isinstance(body, dict) else {}, state)
            except Exception as error:  # a failed turn is an answer, not a dead worker
                answer = {"ok": False, "error": f"{type(error).__name__}: {error}"}
            self._send(200 if answer.get("ok") else 422, answer)

        def log_message(self, format: str, *args: Any) -> None:
            print(json.dumps({"agent": "agent-ask-orama", "request": format % args}), flush=True)

    port = int(os.environ.get("PORT", "8080"))
    print(json.dumps({"agent": "agent-ask-orama", "listening": port}), flush=True)
    # Turns arrive as tasks on lake's agent bus (lake#269); /v1/turn stays for direct calls.
    # Only a claimed task carries a claim; a direct /v1/turn never does (agent-ask-orama#42).
    lake_bus.start_from_env(lambda body: run_turn(body, state, claim=body.get("claim")),
                            "agent-ask-orama")
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
    return 0

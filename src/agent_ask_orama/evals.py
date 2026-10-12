"""Ask Orama's evals: generated from lake's own capability index, graded by rules, run live.

Generated, never hand-written (zetta-bridge `docs/agents/scaffold.md`): the cases come from the
capabilities the live lake serves, so a new capability is a new case without anyone writing one.
Graded deterministically, never by a judge:

- a **change** request must come back as a proposal of that capability, with **no write sent**;
- a **read** request must call that read;
- a **clarify** request names a capability that needs an input the request does not give (an id):
  Ask Orama must send no write and either ask for it or look it up with a read first, never use the
  capability with a value it did not find (change and read cases only sample capabilities whose
  required inputs are the space alone, so they can be done as asked);
- a **Pipeline** request must delegate to `agent-project`, an **opportunity** request to
  `agent-autosuggest`, and an **App** request to `agent-application` with kind `app`;
- **training**, **tuning** and **best-model** requests must delegate to `agent-experiments` with
  kind `experiment`; progress requests use `experiment_status`, and divergence questions use
  `experiment_explain`;
- an **App list** request must call `list_apps`;
- an **App health** request must call `get_app` and `receive_app_events`;
- a **build failure** request must call `list_builds`, `get_build`, and `receive_build_events`;
- a **methodology** question must read `list_methodologies`, affirm runnable support, or decline
  unsupported work with its issue;
- a **solution** question must read `list_solutions` and describe the current entry honestly;
- a **solution readout** request must read the registry, then call `get_roi_readout`;
- a **workspace entities** question (its training experiments, search indexes and agents) must
  read each, by lake's named capability or through `workspace_query` (agent-ask-orama#16);
- a **model score** question ("which of my models scored best") must read `list_models` (through
  `compare_models`) and answer with held-out figures (agent-ask-orama#14);
- a **new agent** request must send the person to Design → Agents or the Agent Factory, and an
  **improve an agent** request to Train → Agents (lake#653, agent-ask-orama#19);
- a turn asked from `/design/agents` or `/design/agent` must speak of designing the agent, and one
  from `/train/agent` of training it, never of the other alone (agent-ask-orama#19);
- no turn may run out of tool rounds (`incomplete`).
- every proposal and read must name a capability that exists (no invented names).

Run against a real lake as a real person:

    LAKE_URL=... LAKE_TOKEN=... CUSTOMER_ID=... uv run ask-orama-evals --out reports/

Writes `reports/<date>-evals.md` and a JSON twin. A score not produced by this runner is not a
score.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import httpx
from openai import OpenAI

from agent_ask_orama.agent import (
    OLD_ENGINE_ISSUE,
    Capability,
    Lake,
    MethodologyCatalog,
    SolutionCatalog,
    Turn,
    answer_turn,
    capability_index,
    engine_operation,
    issue_url,
    with_customer,
)

DELEGATIONS = [
    ("agent-project", "Build me a Pipeline that predicts which accounts will churn next quarter."),
    ("agent-project", "Change my churn Pipeline so it holds out the last month of data."),
    ("agent-autosuggest", "What could I build from the data in this workspace?"),
    ("agent-autosuggest", "Which opportunities does my data support? Rank them."),
    ("agent-application", "Build me an App that shows the highest-risk accounts."),
    ("agent-application", "Change App app-1 to show account risk drivers."),
]

EXPERIMENT_QUESTIONS = [
    ("experiment-train", "experiment", "Train a model on the accounts dataset."),
    ("experiment-tune", "experiment", "Tune my churn model."),
    ("experiment-best-model", "experiment", "Find the best model for customer retention."),
    ("experiment-progress", "experiment_status", "How is study study-7 progressing?"),
    ("experiment-diverged", "experiment_explain", "Why did run run-4 diverge?"),
]

METHODOLOGY_QUESTIONS = [
    ("M-3", "Can you segment my customers?"),
    ("M-14", "Can you do speech analytics?"),
]

SOLUTION_QUESTIONS = [
    ("S-1", "Is solution S-1 available for production use?"),
    ("B-1", "Can I build solution B-1?"),
]

# Where a person is sent for agent work (lake#653): `design` is Design → Agents or the Agent
# Factory, `train` is Train → Agents.
AGENT_PLACE_QUESTIONS = [
    ("agent-new", "design",
     "I want a new agent that triages our support tickets. Where do I make it?"),
    ("agent-improve", "train",
     "My support triage agent's answers are getting worse. How do I make it better?"),
]

# A question asked from one of Lake Console's agent pages, and the work the answer must speak of.
AGENT_PAGE_QUESTIONS = [
    ("page-design-agents", "design", {"path": "/design/agents"}, "What can I do here?"),
    ("page-design-agent", "design", {"path": "/design/agent", "id": "agent-1"},
     "What should I do next with this agent?"),
    ("page-train-agent", "train", {"path": "/train/agent", "id": "agent-1"},
     "What should I do next with this agent?"),
]

# The reads that answer "which experiments, search indexes and agents": each set is one entity,
# by lake's name or the engine's.
WORKSPACE_ENTITY_READS = (
    frozenset({"list_experiments", "list_studies"}),
    frozenset({"list_indexes"}),
    frozenset({"list_agents"}),
)


@dataclass
class Case:
    id: str
    # change | read | clarify | delegate | experiment* | app_* | methodology | solution
    # | model_scores | workspace_entities
    kind: str
    message: str
    expect: str     # the capability, the agent key, or `design` / `train` for agent work
    page: dict[str, Any] = field(default_factory=dict)  # the page the turn is asked from


@dataclass
class Graded:
    case: Case
    passed: bool
    reasons: list[str]
    answer: dict[str, Any]


def generate(index: dict[str, Capability], changes: int = 8, reads: int = 6,
             clarify: int = 6, seed: int = 7) -> list[Case]:
    """Cases from the live index: changes and reads that can be done as asked, requests that
    need an input they do not give, and the delegations."""
    rng = random.Random(seed)
    lookup = lambda c: c.read and c.name.startswith(("list_", "get_"))  # noqa: E731
    writes = sorted(c.name for c in index.values() if not c.read and not c.required)
    lookups = sorted(c.name for c in index.values() if lookup(c) and not c.required)
    needing = sorted(c.name for c in index.values() if c.required and (lookup(c) or not c.read))
    cases: list[Case] = []

    def asked(name: str) -> str:
        summary = index[name].summary or name.replace("_", " ")
        return summary[0].lower() + summary[1:]

    for name in rng.sample(writes, min(changes, len(writes))):
        cases.append(Case(f"change-{name}", "change",
                          f"Please do this for me: {asked(name)}. Use sensible values and tell "
                          f"me what you would do.", name))
    for name in rng.sample(lookups, min(reads, len(lookups))):
        cases.append(Case(f"read-{name}", "read", f"{asked(name)[0].upper() + asked(name)[1:]}, "
                          "please.", name))
    for name in rng.sample(needing, min(clarify, len(needing))):
        cases.append(Case(f"clarify-{name}", "clarify", f"Please {asked(name)}.", name))
    for number, (agent, message) in enumerate(DELEGATIONS):
        cases.append(Case(f"delegate-{agent}-{number}", "delegate", message, agent))
    for case_id, turn_kind, message in EXPERIMENT_QUESTIONS:
        cases.append(Case(case_id, turn_kind, message, "agent-experiments"))
    cases.extend([
        Case("apps-list", "app_list", "What Apps do I have?", "list_apps"),
        Case("app-health", "app_health", "Is App app-1 healthy?", "app-1"),
        Case("build-last-failure", "build_failure",
             "Why did the last build for App app-1 fail?", "app-1"),
    ])
    for methodology, message in METHODOLOGY_QUESTIONS:
        cases.append(Case(f"methodology-{methodology.lower()}", "methodology", message,
                          methodology))
    for solution, message in SOLUTION_QUESTIONS:
        cases.append(Case(f"solution-{solution.lower()}", "solution", message, solution))
    cases.append(Case("solution-roi-readout", "solution_readout",
                      "Show the measured ROI readout for solution Project retention.",
                      "get_roi_readout"))
    cases.append(Case("workspace-entities", "workspace_entities",
                      "Which training experiments, search indexes and agents do I have in this "
                      "workspace?", "list_experiments,list_indexes,list_agents"))
    cases.append(Case("model-scores", "model_scores",
                      "Which of my trained models scored best on held-out AUC?", "list_models"))
    for case_id, work, message in AGENT_PLACE_QUESTIONS:
        cases.append(Case(case_id, "agent_place", message, work))
    for case_id, work, page, message in AGENT_PAGE_QUESTIONS:
        cases.append(Case(case_id, "agent_page", message, work, page))
    return cases


def grade(case: Case, answer: dict[str, Any], index: dict[str, Capability],
          writes_sent: list[str], methodologies: MethodologyCatalog | None = None,
          solutions: SolutionCatalog | None = None) -> Graded:
    reasons: list[str] = []
    named = [p["capability"] for p in answer["proposals"]] + [r["capability"]
                                                               for r in answer["reads"]]
    invented = [name for name in named if name not in index]
    if invented:
        reasons.append(f"named capabilities lake does not have: {invented}")
    if writes_sent:
        reasons.append(f"sent writes without confirmation: {writes_sent}")
    if answer.get("incomplete"):
        reasons.append("ran out of tool rounds before answering")
    if case.kind == "change":
        if case.expect not in [p["capability"] for p in answer["proposals"]]:
            reasons.append(f"did not propose {case.expect}")
    elif case.kind == "read":
        if case.expect not in [r["capability"] for r in answer["reads"]] and not any(
                r["capability"] == "workspace_query" for r in answer["reads"]):
            reasons.append(f"did not read {case.expect}")
    elif case.kind == "clarify":
        used = case.expect in [p["capability"] for p in answer["proposals"]] + [
            r["capability"] for r in answer["reads"]]
        looked_up = any(r["capability"] != case.expect for r in answer["reads"])
        if used and not looked_up:
            reasons.append(f"used {case.expect} without finding the input it needs")
        if not used and "?" not in answer["reply"]:
            reasons.append(f"neither asked for {sorted(index[case.expect].required)} nor found it")
    elif case.kind == "delegate":
        matching = [d for d in answer["delegations"] if d["agent"] == case.expect]
        if not matching:
            reasons.append(f"did not delegate to {case.expect}")
        elif case.expect == "agent-application" and matching[0].get("kind") != "app":
            reasons.append("did not delegate ApplicationAgent work with kind app")
    elif case.kind in {"experiment", "experiment_status", "experiment_explain"}:
        matching = [d for d in answer["delegations"] if d["agent"] == case.expect]
        if not matching:
            reasons.append("did not delegate to agent-experiments")
        elif matching[0].get("kind") != case.kind:
            reasons.append(f"did not use ExperimentsAgent turn kind {case.kind}")
        reply = answer["reply"].lower()
        if case.kind == "experiment":
            if not any(word in reply for word in ("proposal", "proposed")):
                reasons.append("did not summarize the study as a proposal")
            if not any(word in reply for word in ("confirm", "review")):
                reasons.append("did not tell the person to review or confirm the proposal")
        elif case.kind == "experiment_status":
            if not any(word in reply for word in ("study", "trial", "progress", "budget")):
                reasons.append("did not summarize study progress")
        elif "diverg" not in reply:
            reasons.append("did not summarize the divergence explanation")
    elif case.kind == "model_scores":
        if case.expect not in engine_reads(answer):
            reasons.append(f"did not read {case.expect}")
        reply = answer["reply"].lower()
        if "held-out" not in reply and "held out" not in reply and "no models" not in reply:
            reasons.append("did not answer with held-out scores")
    elif case.kind == "workspace_entities":
        # Each of an experiment, a search index and an agent, read by lake's name or the
        # engine's (agent-ask-orama#16).
        read = read_anything(answer)
        for alternatives in WORKSPACE_ENTITY_READS:
            if not read & alternatives:
                reasons.append(f"did not read {' or '.join(sorted(alternatives))}")
    elif case.kind == "agent_place":
        places = places_named(answer["reply"])
        if case.expect == "design" and not places & {"design → agents", "agent factory"}:
            reasons.append("did not send a new agent to Design → Agents or the Agent Factory")
        if case.expect == "train" and "train → agents" not in places:
            reasons.append("did not send improving an agent to Train → Agents")
    elif case.kind == "agent_page":
        own, other = ("design", "train") if case.expect == "design" else ("train", "design")
        # Naming the other page ("train it on Train → Agents") is offering it, not speaking of it.
        said = re.sub(r"(design|train) → agents", "", arrows(answer["reply"]))
        mentions = {work: len(re.findall(rf"\b{work}", said)) for work in (own, other)}
        if not mentions[own]:
            reasons.append(f"did not speak of {own}ing the agent on {case.page['path']}")
        elif mentions[other] > mentions[own]:
            reasons.append(f"spoke of {other}ing more than {own}ing on {case.page['path']}")
    elif case.kind == "app_list":
        require_reads(answer, ["list_apps"], reasons)
    elif case.kind == "app_health":
        require_reads(answer, ["get_app", "receive_app_events"], reasons)
    elif case.kind == "build_failure":
        require_reads(answer, ["list_builds", "get_build", "receive_build_events"], reasons)
    elif case.kind == "methodology":
        if "list_methodologies" not in engine_reads(answer):
            reasons.append("did not read list_methodologies")
        if methodologies is None or not methodologies.loaded:
            reasons.append("eval did not load the methodology registry")
        else:
            item = methodologies.methodologies.get(case.expect)
            runnable = bool(item and item.get("runnable"))
            reply = answer["reply"].lower()
            negative = any(phrase in reply for phrase in (
                "cannot",
                "can't",
                "does not support",
                "doesn't support",
                "not available",
                "not runnable",
                "not supported",
            ))
            if runnable:
                affirmative = any(word in reply for word in ("yes", "can", "runnable",
                                                              "supported"))
                if not affirmative or negative:
                    reasons.append(f"did not affirm runnable {case.expect}")
            else:
                issue = str((item or {}).get("issue") or OLD_ENGINE_ISSUE)
                if not negative:
                    reasons.append(f"did not decline unsupported {case.expect}")
                if issue.lower() not in reply and issue_url(issue).lower() not in reply:
                    reasons.append(f"did not name {issue} for unsupported {case.expect}")
    elif case.kind in {"solution", "solution_readout"}:
        solution_read = any(
            read.get("capability") == "workspace_query"
            and (read.get("input") or {}).get("capability") == "list_solutions"
            for read in answer["reads"]
        )
        if not solution_read:
            reasons.append("did not read list_solutions")
        if solutions is None or not solutions.loaded:
            reasons.append("eval did not load the solution registry")
        elif case.kind == "solution_readout":
            if case.expect not in engine_reads(answer):
                reasons.append(f"did not read {case.expect}")
        else:
            grade_solution_answer(case, answer["reply"], solutions, reasons)
    return Graded(case, not reasons, reasons, answer)


def places_named(reply: str) -> set[str]:
    """The agent places a reply names, however its arrow is written (→, ->, >, ›)."""
    text = arrows(reply)
    return {place for place in ("design → agents", "train → agents", "agent factory")
            if place in text}


def arrows(reply: str) -> str:
    """The reply in lower case, unformatted, with every page arrow written ` → `."""
    text = re.sub(r"\s*(?:→|->|›|>)\s*", " → ", reply.lower().replace("*", "").replace("`", ""))
    return re.sub(r"\s+", " ", text)


def engine_reads(answer: dict[str, Any]) -> set[str]:
    """The workspace engine reads a turn made, named either way (lake#650): through
    workspace_query by the engine's name, or as the named lake capability."""
    names: set[str] = set()
    for read in answer["reads"]:
        operation, _ = engine_operation(str(read.get("capability") or ""),
                                        read.get("input") or {})
        if operation:
            names.add(operation)
    return names


def read_anything(answer: dict[str, Any]) -> set[str]:
    """Every capability a turn read, lake's names and the engine's."""
    return {str(read.get("capability")) for read in answer["reads"]} | engine_reads(answer)


def require_reads(answer: dict[str, Any], expected: list[str], reasons: list[str]) -> None:
    """Require the named lake reads in a fixed behavior case."""
    called = {read.get("capability") for read in answer["reads"]}
    for capability in expected:
        if capability not in called:
            reasons.append(f"did not read {capability}")


def grade_solution_answer(case: Case, reply: str, catalog: SolutionCatalog,
                          reasons: list[str]) -> None:
    """Grade availability language against the live solution entry."""
    lowered = reply.lower()
    item = catalog.solutions.get(case.expect)
    if catalog.old_engine:
        if "not deployed" not in lowered and "no solution registry" not in lowered:
            reasons.append("did not explain that solution operations are not deployed")
        return
    if item is None:
        if "not available" not in lowered and "not in" not in lowered:
            reasons.append(f"did not explain that {case.expect} is absent")
        return
    negative = any(phrase in lowered for phrase in (
        "cannot",
        "can't",
        "not available",
        "not runnable",
        "not supported",
        "not production-ready",
        "not ready for production",
    ))
    if item.get("status") == "sketch":
        condition = str(item.get("promotion_condition") or "").lower()
        issue = str(item.get("issue") or "")
        if not negative and "sketch" not in lowered:
            reasons.append(f"did not decline sketch {case.expect}")
        if condition and condition not in lowered:
            if issue.lower() not in lowered and issue_url(issue).lower() not in lowered:
                reasons.append(f"did not name the promotion condition or issue for {case.expect}")
        return
    if item.get("runnable"):
        affirmative = any(word in lowered for word in ("yes", "available", "runnable",
                                                        "production"))
        if not affirmative or negative:
            reasons.append(f"did not affirm runnable {case.expect}")
        return
    missing = item.get("missing") or item.get("missing_components") or []
    missing_terms = [
        str(component.get("issue") or component.get("name") or component.get("id") or "").lower()
        for component in missing
        if isinstance(component, dict)
    ]
    if "pipeline" not in lowered or not any(word in lowered for word in ("build", "preview")):
        reasons.append(f"did not explain the buildable Pipeline for {case.expect}")
    if missing_terms and not any(term and term in lowered for term in missing_terms):
        reasons.append(f"did not name a missing production component for {case.expect}")


def read_methodologies(lake: Lake, index: dict[str, Capability],
                       customer_id: str) -> MethodologyCatalog:
    """Read the live registry once so methodology evals know the expected answer."""
    catalog = MethodologyCatalog()
    capability = index.get("workspace_query")
    if capability is None:
        return catalog
    payload = with_customer(capability, {"capability": "list_methodologies", "input": {}},
                            customer_id)
    result = lake.call(capability.name, payload, read=capability.get)
    catalog.observe(payload["capability"], result)
    return catalog


def read_solutions(lake: Lake, index: dict[str, Capability],
                   customer_id: str) -> SolutionCatalog:
    """Read the live registry once so solution evals know the expected answer."""
    catalog = SolutionCatalog()
    capability = index.get("workspace_query")
    if capability is None:
        return catalog
    payload = with_customer(capability, {"capability": "list_solutions", "input": {}},
                            customer_id)
    result = lake.call(capability.name, payload, read=capability.get)
    catalog.observe(payload["capability"], result)
    return catalog


class Recording(httpx.BaseTransport):
    """The real transport, noting every write lake receives (proposals must send none)."""

    def __init__(self, index: dict[str, Capability],
                 inner: httpx.BaseTransport | None = None) -> None:
        self.inner = inner or httpx.HTTPTransport()
        self.writes: list[str] = []
        # A read is a read however it is sent: lake takes some reads as a POST too (post_alias),
        # as Ask Orama sends the connected-tools listing every turn (lake#652).
        self.read_posts = {f"/v1/{capability.name}" for capability in index.values()
                           if capability.read}

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        read_posts = self.read_posts | {"/v1/agent_turn", "/v1/list_mcp_connection_tools"}
        if request.method == "POST" and request.url.path not in read_posts:
            self.writes.append(request.url.path)
        return self.inner.handle_request(request)


def run_case(case: Case, base: Turn, index: dict[str, Capability], client: Any, model: str,
             inner: httpx.BaseTransport | None = None,
             methodologies: MethodologyCatalog | None = None,
             solutions: SolutionCatalog | None = None) -> Graded:
    """One case as a turn of its own, asked from its page, graded with the writes lake saw."""
    recording = Recording(index, inner)
    turn = Turn(**{**asdict(base), "message": case.message, "page": case.page})
    lake = Lake(turn, transport=recording)
    try:
        answer = answer_turn(turn, [], client, model, lake).as_dict()
    except Exception as error:  # a crash is a failed case, not a skipped one
        answer = {"reply": f"{type(error).__name__}: {error}", "reads": [], "proposals": [],
                  "delegations": [], "rounds": 0}
    finally:
        lake.close()
    return grade(case, answer, index, recording.writes, methodologies, solutions)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Ask Orama's generated evals live.")
    parser.add_argument("--out", type=Path, default=Path("reports"))
    parser.add_argument("--model", default=os.environ.get("ASK_ORAMA_MODEL", "gpt-5.5"))
    args = parser.parse_args()
    base = Turn(message="", lake_url=os.environ["LAKE_URL"], lake_token=os.environ["LAKE_TOKEN"],
                customer_id=os.environ.get("CUSTOMER_ID", ""))
    probe = Lake(base)
    index = capability_index(probe.openapi())
    methodologies = read_methodologies(probe, index, base.customer_id)
    solutions = read_solutions(probe, index, base.customer_id)
    probe.close()
    client = OpenAI()
    results: list[Graded] = []
    for case in generate(index):
        results.append(run_case(case, base, index, client, args.model, methodologies=methodologies,
                                solutions=solutions))
    passed = sum(result.passed for result in results)
    args.out.mkdir(parents=True, exist_ok=True)
    stamp = date.today().isoformat()
    (args.out / f"{stamp}-evals.json").write_text(json.dumps(
        [{"case": asdict(r.case), "passed": r.passed, "reasons": r.reasons, "answer": r.answer}
         for r in results], indent=1, default=str))
    lines = [f"# Ask Orama evals, {stamp}", "",
             f"**{passed} / {len(results)} passed** with `{args.model}` against `{base.lake_url}`.",
             "Generated from lake's live capability index; graded by rules (evals.py), no judge.",
             "", "| Case | Kind | Expected | Result |", "|---|---|---|---|"]
    for result in results:
        lines.append(f"| `{result.case.id}` | {result.case.kind} | `{result.case.expect}` | "
                     + ("pass" if result.passed else "FAIL: " + "; ".join(result.reasons)) + " |")
    (args.out / f"{stamp}-evals.md").write_text("\n".join(lines) + "\n")
    print(f"{passed}/{len(results)} passed")
    return 0 if passed == len(results) else 2

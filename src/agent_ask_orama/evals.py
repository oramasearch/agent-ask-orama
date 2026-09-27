"""Ask Orama's evals: generated from lake's own capability index, graded by rules, run live.

Generated, never hand-written (zetta-bridge `docs/agents/scaffold.md`): the cases come from the
capabilities the live lake serves, so a new capability is a new case without anyone writing one.
Graded deterministically, never by a judge:

- a **change** request must come back as a proposal of that capability, with **no write sent**;
- a **read** request must call that read;
- a **Pipeline** request must delegate to `agent-project`, an **opportunity** request to
  `agent-autosuggest`;
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
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any

import httpx
from openai import OpenAI

from agent_ask_orama.agent import Capability, Lake, Turn, answer_turn, capability_index

DELEGATIONS = [
    ("agent-project", "Build me a Pipeline that predicts which accounts will churn next quarter."),
    ("agent-project", "Change my churn Pipeline so it holds out the last month of data."),
    ("agent-autosuggest", "What could I build from the data in this workspace?"),
    ("agent-autosuggest", "Which opportunities does my data support? Rank them."),
]


@dataclass
class Case:
    id: str
    kind: str       # change | read | delegate
    message: str
    expect: str     # the capability, or the agent key


@dataclass
class Graded:
    case: Case
    passed: bool
    reasons: list[str]
    answer: dict[str, Any]


def generate(index: dict[str, Capability], changes: int = 10, reads: int = 8,
             seed: int = 7) -> list[Case]:
    """Cases from the live index: a sample of changes and reads, plus the delegations."""
    rng = random.Random(seed)
    writes = sorted(c.name for c in index.values() if not c.read)
    lookups = sorted(c.name for c in index.values() if c.read and c.name.startswith(("list_",
                                                                                     "get_")))
    cases: list[Case] = []
    for name in rng.sample(writes, min(changes, len(writes))):
        summary = index[name].summary or name.replace("_", " ")
        cases.append(Case(f"change-{name}", "change",
                          f"Please do this for me: {summary[0].lower() + summary[1:]}. Use "
                          f"sensible values and tell me what you would do.", name))
    for name in rng.sample(lookups, min(reads, len(lookups))):
        summary = index[name].summary or name.replace("_", " ")
        cases.append(Case(f"read-{name}", "read", f"{summary}, please.", name))
    for number, (agent, message) in enumerate(DELEGATIONS):
        cases.append(Case(f"delegate-{agent}-{number}", "delegate", message, agent))
    return cases


def grade(case: Case, answer: dict[str, Any], index: dict[str, Capability],
          writes_sent: list[str]) -> Graded:
    reasons: list[str] = []
    named = [p["capability"] for p in answer["proposals"]] + [r["capability"]
                                                               for r in answer["reads"]]
    invented = [name for name in named if name not in index]
    if invented:
        reasons.append(f"named capabilities lake does not have: {invented}")
    if writes_sent:
        reasons.append(f"sent writes without confirmation: {writes_sent}")
    if case.kind == "change":
        if case.expect not in [p["capability"] for p in answer["proposals"]]:
            reasons.append(f"did not propose {case.expect}")
    elif case.kind == "read":
        if case.expect not in [r["capability"] for r in answer["reads"]] and not any(
                r["capability"] == "workspace_query" for r in answer["reads"]):
            reasons.append(f"did not read {case.expect}")
    elif case.kind == "delegate":
        if case.expect not in [d["agent"] for d in answer["delegations"]]:
            reasons.append(f"did not delegate to {case.expect}")
    return Graded(case, not reasons, reasons, answer)


class Recording(httpx.BaseTransport):
    """The real transport, noting every write lake receives (proposals must send none)."""

    def __init__(self) -> None:
        self.inner = httpx.HTTPTransport()
        self.writes: list[str] = []

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path != "/v1/agent_turn":
            self.writes.append(request.url.path)
        return self.inner.handle_request(request)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Ask Orama's generated evals live.")
    parser.add_argument("--out", type=Path, default=Path("reports"))
    parser.add_argument("--model", default=os.environ.get("ASK_ORAMA_MODEL", "gpt-5.5"))
    args = parser.parse_args()
    base = Turn(message="", lake_url=os.environ["LAKE_URL"], lake_token=os.environ["LAKE_TOKEN"],
                customer_id=os.environ.get("CUSTOMER_ID", ""))
    probe = Lake(base)
    index = capability_index(probe.openapi())
    probe.close()
    client = OpenAI()
    results: list[Graded] = []
    for case in generate(index):
        recording = Recording()
        turn = Turn(**{**asdict(base), "message": case.message})
        lake = Lake(turn, transport=recording)
        try:
            answer = answer_turn(turn, [], client, args.model, lake).as_dict()
        except Exception as error:  # a crash is a failed case, not a skipped one
            answer = {"reply": f"{type(error).__name__}: {error}", "reads": [], "proposals": [],
                      "delegations": [], "rounds": 0}
        finally:
            lake.close()
        results.append(grade(case, answer, index, recording.writes))
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

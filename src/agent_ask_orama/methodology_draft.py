# SPDX-License-Identifier: MIT

"""Ask Orama writes the first draft of a workspace methodology (lake#688).

Lake's New Methodology drawer sends Ask Orama a `methodology_draft` turn through `agent_turn`: the
person's description, with the name and kind of target they chose in `context`. The answer is the
three files of a methodology (lake `docs/api/methodologies.md`): `methodology.json`, `methodology.py`
with fit, predict and score, and `requirements.lock`, every package in it pinned with the SHA-256 of
each wheel the index has for that version.

The model writes the manifest, the code and the package pins; it never writes a hash. This module
looks each pin up in the package index, assembles the files, and checks them the way Lake's
Validate does before running anything (the manifest's fields, fit/predict/score at module level,
every lock line pinned and hashed). A draft that fails gets one more round with the findings; one
that still fails is answered with `ok: false` and its findings, and Lake offers its own template
instead. Lake checks whatever it is given again before offering it: these checks save a round
trip, they are not the authority.

Nothing is written: the person reviews the draft in the drawer, and Create commits it.
"""

from __future__ import annotations

import ast
import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
from openai import OpenAI

DRAFT_PROMPT_VERSION = "methodology_draft_v1"
PROMPTS = Path(__file__).parent / "prompts"
MAX_ROUNDS = 2
MANIFEST = "methodology.json"
ENTRYPOINT = "methodology.py"
LOCK = "requirements.lock"
INPUT_KINDS = ("tabular", "text", "time_series", "graph", "image", "audio", "document")
TARGET_KINDS = ("binary", "multiclass", "regression", "none")
PARAMETER_KINDS = ("int", "float", "categorical", "bool")
PIN = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([A-Za-z0-9][A-Za-z0-9.+!_-]*)$")
PYPI = "https://pypi.org/pypi"

# (name, version) -> the sha256 of every wheel the index has for it; raises LookupError.
HashLookup = Callable[[str, str], list[str]]


def pypi_wheel_hashes(name: str, version: str, client: httpx.Client | None = None) -> list[str]:
    """Every wheel's SHA-256 for `name==version` on the Python package index."""
    owned = client is None
    client = client or httpx.Client(timeout=20.0, headers={"User-Agent": "agent-ask-orama"})
    try:
        response = client.get(f"{PYPI}/{name}/{version}/json")
    except httpx.HTTPError as error:
        raise LookupError(f"{name}=={version}: the package index could not be reached "
                          f"({type(error).__name__})") from None
    finally:
        if owned:
            client.close()
    if response.status_code == 404:
        raise LookupError(f"{name}=={version} is not on the package index")
    if response.status_code != 200:
        raise LookupError(f"{name}=={version}: the package index answered HTTP "
                          f"{response.status_code}")
    hashes = sorted({str(entry.get("digests", {}).get("sha256", "")).lower()
                     for entry in response.json().get("urls") or []
                     if entry.get("packagetype") == "bdist_wheel"} - {""})
    if not hashes:
        raise LookupError(f"{name}=={version} has no wheels; methodologies install wheels only")
    return hashes


@dataclass
class Finding:
    check: str
    ok: bool
    message: str
    file: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {"check": self.check, "ok": self.ok, "message": self.message, "file": self.file}


@dataclass
class Draft:
    name: str = ""
    reason: str = ""
    files: list[dict[str, str]] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return bool(self.files) and all(finding.ok for finding in self.findings)


def lock_text(packages: list[str], lookup: HashLookup) -> tuple[str, list[Finding]]:
    """requirements.lock for the pins, each with every wheel's hash (pip-compile's layout)."""
    lines: list[str] = []
    findings: list[Finding] = []
    seen: set[str] = set()
    for pin in packages:
        match = PIN.match(str(pin).strip())
        if not match:
            findings.append(Finding("packages", False,
                                    f"{pin!r} is not pinned; write name==version", LOCK))
            continue
        name, version = match.groups()
        if name.lower() in seen:
            continue
        seen.add(name.lower())
        try:
            hashes = lookup(name, version)
        except LookupError as error:
            findings.append(Finding("packages", False, str(error), LOCK))
            continue
        lines.append(f"{name}=={version} \\")
        lines.extend(f"    --hash=sha256:{digest}" + (" \\" if i + 1 < len(hashes) else "")
                     for i, digest in enumerate(hashes))
    text = ("# Pinned and hashed; installed with --require-hashes --no-deps, wheels only.\n"
            + "\n".join(lines) + "\n") if lines else ""
    return text, findings


def check_manifest(manifest: Any) -> list[Finding]:
    """What Lake's read_manifest refuses, said the same way."""
    problems: list[Finding] = []

    def fail(check: str, message: str) -> None:
        problems.append(Finding(check, False, message, MANIFEST))

    if not isinstance(manifest, dict):
        return [Finding("manifest", False, "the manifest is not a JSON object", MANIFEST)]
    name = manifest.get("name")
    if not isinstance(name, str) or not 0 < len(name.encode()) <= 200:
        fail("manifest.name", "a name of 1 to 200 bytes")
    inputs = manifest.get("inputs")
    if not isinstance(inputs, dict):
        fail("manifest.inputs", "inputs is an object with kinds and target")
    else:
        kinds = inputs.get("kinds")
        if not isinstance(kinds, list) or not kinds or any(k not in INPUT_KINDS for k in kinds):
            fail("manifest.inputs.kinds", "one or more of " + ", ".join(INPUT_KINDS))
        target = inputs.get("target")
        if not isinstance(target, dict) or target.get("kind") not in TARGET_KINDS:
            fail("manifest.inputs.target.kind", "one of " + ", ".join(TARGET_KINDS))
        elif bool(target.get("required")) == (target.get("kind") == "none"):
            fail("manifest.inputs.target.required",
                 "required is false exactly when the target's kind is none")
    metrics = manifest.get("metrics")
    if not isinstance(metrics, list) or not metrics or not all(
            isinstance(m, str) and re.fullmatch(r"[a-z][a-z0-9_]*", m) for m in metrics):
        fail("manifest.metrics", "one or more base metric names, such as auc")
    names: set[str] = set()
    for i, parameter in enumerate(manifest.get("parameters") or []):
        check = f"manifest.parameters[{i}]"
        if not isinstance(parameter, dict) or parameter.get("kind") not in PARAMETER_KINDS:
            fail(check, "a parameter has a name and a kind: " + ", ".join(PARAMETER_KINDS))
            continue
        pname = parameter.get("name")
        if not isinstance(pname, str) or not pname or pname in names:
            fail(check, "each parameter has a unique name")
        names.add(str(pname))
        kind, default = parameter["kind"], parameter.get("default")
        if kind in ("int", "float"):
            low, high = parameter.get("minimum"), parameter.get("maximum")
            numeric = all(isinstance(v, (int, float)) and not isinstance(v, bool)
                          for v in (low, high, default))
            if not numeric or not low <= default <= high:
                fail(check, f"{pname}: a default inside its minimum and maximum")
            elif parameter.get("log") and low <= 0:
                fail(check, f"{pname}: a log-scaled parameter's minimum is above zero")
        elif kind == "categorical":
            choices = parameter.get("choices")
            if not isinstance(choices, list) or not choices or default not in choices:
                fail(check, f"{pname}: choices, with the default one of them")
        elif not isinstance(default, bool):
            fail(check, f"{pname}: a bool's default is true or false")
    return problems


def check_entrypoint(source: str, explain: bool) -> list[Finding]:
    """fit, predict and score (and explain when declared) defined at module level, unrun."""
    try:
        tree = ast.parse(source, filename=ENTRYPOINT)
    except SyntaxError as error:
        return [Finding("entrypoint", False, f"line {error.lineno}: {error.msg}", ENTRYPOINT)]
    defined = {node.name for node in tree.body
               if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    needed = ["fit", "predict", "score"] + (["explain"] if explain else [])
    return [Finding(f"entrypoint.{name}", False, f"{ENTRYPOINT} does not define {name} at "
                    "module level", ENTRYPOINT) for name in needed if name not in defined]


def assemble(proposed: dict[str, Any], lookup: HashLookup) -> Draft:
    """The three files from the model's answer, with what is wrong with them."""
    manifest = dict(proposed.get("manifest") or {}) if isinstance(proposed.get("manifest"),
                                                                  dict) else {}
    manifest.update({"interface": 1, "entrypoint": ENTRYPOINT, "packages": LOCK})
    if not manifest.get("name") and proposed.get("name"):
        manifest["name"] = proposed["name"]
    manifest.setdefault("explain", False)
    manifest.setdefault("parameters", [])
    source = proposed.get("source") if isinstance(proposed.get("source"), str) else ""
    packages = proposed.get("packages") if isinstance(proposed.get("packages"), list) else []
    lock, lock_findings = lock_text(packages, lookup)
    findings = check_manifest(manifest) + check_entrypoint(source, bool(manifest.get("explain")))
    findings += lock_findings
    ordered = {key: manifest[key] for key in (
        "interface", "name", "description", "entrypoint", "inputs", "parameters", "metrics",
        "explain", "packages", "resources") if key in manifest}
    ordered.update({k: v for k, v in manifest.items() if k not in ordered})
    return Draft(name=str(manifest.get("name") or ""),
                 reason=str(proposed.get("reason") or ""),
                 files=[{"path": MANIFEST, "contents": json.dumps(ordered, indent=2) + "\n"},
                        {"path": ENTRYPOINT, "contents": source},
                        {"path": LOCK, "contents": lock}],
                 findings=findings)


def request_text(description: str, context: dict[str, Any]) -> str:
    lines = [f"What the methodology should do: {description.strip()}"]
    if context.get("name"):
        lines.append(f"Its name: {context['name']}")
    if context.get("target_kind") in TARGET_KINDS:
        lines.append(f"Its target's kind: {context['target_kind']}")
    if isinstance(context.get("columns"), list) and context["columns"]:
        lines.append("The dataset's columns: " + ", ".join(map(str, context["columns"][:200])))
    return "\n".join(lines)


def draft_methodology(description: str, context: dict[str, Any], client: OpenAI, model: str,
                      lookup: HashLookup | None = None) -> tuple[Draft, int]:
    """A checked draft for the description, and the model rounds it took."""
    lookup = lookup or (lambda name, version: pypi_wheel_hashes(name, version))
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": (PROMPTS / f"{DRAFT_PROMPT_VERSION}.md").read_text()},
        {"role": "user", "content": request_text(description, context)},
    ]
    draft = Draft()
    for round_number in range(1, MAX_ROUNDS + 1):
        message = client.chat.completions.create(
            model=model, messages=messages,
            response_format={"type": "json_object"}).choices[0].message
        content = message.content or ""
        messages.append({"role": "assistant", "content": content})
        try:
            proposed = json.loads(content)
        except json.JSONDecodeError:
            proposed = None
        if not isinstance(proposed, dict):
            draft = Draft(findings=[Finding("draft", False, "the answer was not a JSON object")])
        else:
            draft = assemble(proposed, lookup)
            if context.get("name") and not proposed.get("manifest", {}).get("name"):
                draft.name = str(context["name"])
        if draft.ok:
            return draft, round_number
        failing = [f"- {f.check}: {f.message}" for f in draft.findings if not f.ok]
        messages.append({"role": "user", "content": "These checks failed; answer the whole JSON "
                         "object again with them fixed:\n" + "\n".join(failing)})
    return draft, MAX_ROUNDS


def methodology_draft_turn(body: dict[str, Any], client: OpenAI, model: str,
                           lookup: HashLookup | None = None) -> dict[str, Any]:
    """A `methodology_draft` turn's answer, as lake's agent bus publishes it."""
    description = str(body.get("message") or "")
    context = body.get("context") if isinstance(body.get("context"), dict) else {}
    draft, rounds = draft_methodology(description, context, client, model, lookup)
    findings = [finding.as_dict() for finding in draft.findings]
    if not draft.ok:
        failing = "; ".join(f"{f.check}: {f.message}" for f in draft.findings if not f.ok)
        return {"ok": False, "rounds": rounds, "findings": findings,
                "error": f"Ask Orama could not write a draft that passes the checks ({failing})"}
    return {"ok": True, "rounds": rounds,
            "reply": f"I wrote a first version of {draft.name}: {draft.reason}".strip(),
            "result": {"kind": "methodology_draft", "name": draft.name, "reason": draft.reason,
                       "files": draft.files, "findings": findings,
                       "prompt_version": DRAFT_PROMPT_VERSION}}

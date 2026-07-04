"""Agentic review support: verdict contract, diff computation, reviewer prep.

A reviewer is just a worker with a different prompt — a fresh process
in a fresh attempt directory, never the implementer session. It reads
the task file(s) and the diff under review and writes a structured
verdict to ``verdict.json`` in its attempt directory:

.. code-block:: json

    {"pass": true,
     "findings": [{"task_id": "1.2", "severity": "blocker",
                   "summary": "...", "detail": "..."}]}

The gate fails when ``pass`` is false or any finding is a ``blocker``;
warnings alone do not fail. A missing or invalid verdict after a
Stop-completed reviewer attempt fails CLOSED.
"""

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import ValidationError

from coordinator.attempt import PreparedAttempt
from coordinator.attempt import builtin_data_text
from coordinator.attempt import write_hooks_fragment
from coordinator.statedir import attempt_dir

VERDICT_FILENAME = "verdict.json"
DIFF_FILENAME = "review_diff.patch"
MAX_DIFF_BYTES = 512 * 1024
_TRUNCATION_NOTICE = "\n\n[diff truncated here — it exceeded the size cap; judge what is visible]\n"
# git's canonical empty-tree object id — the diff base when a scope
# starts at the repository's root commit (which has no parent).
_EMPTY_TREE_HASH = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


class VerdictError(Exception):
    pass


class Finding(BaseModel):
    task_id: str | None = None
    severity: Literal["blocker", "warning"]
    summary: str
    detail: str = ""


class Verdict(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    passed: bool = Field(alias="pass")
    findings: list[Finding] = []

    def blocks(self) -> bool:
        return not self.passed or any(finding.severity == "blocker" for finding in self.findings)


def parse_verdict(path: Path) -> Verdict:
    """Parse the reviewer's verdict file; raises :class:`VerdictError` on any problem."""
    if not path.is_file():
        raise VerdictError(f"reviewer wrote no verdict file at {path}")
    try:
        data = json.loads(path.read_text())
    except ValueError as e:
        raise VerdictError(f"verdict file {path} is not valid JSON: {e}")
    try:
        return Verdict.model_validate(data)
    except ValidationError as e:
        raise VerdictError(f"verdict file {path} does not match the verdict schema: {e}")


def format_findings(verdict: Verdict) -> str:
    if not verdict.findings:
        return "(no findings)"
    lines = []
    for finding in verdict.findings:
        scope = f" (task {finding.task_id})" if finding.task_id else ""
        detail = f": {finding.detail}" if finding.detail else ""
        lines.append(f"[{finding.severity}]{scope} {finding.summary}{detail}")
    return "\n".join(lines)


def build_review_diff(cwd: Path, commits: list[str], max_bytes: int = MAX_DIFF_BYTES) -> str:
    """The combined diff of a contiguous commit range (sequential increment 1)."""
    if not commits:
        return "(no commits recorded in the review scope)\n"
    base = f"{commits[0]}^"
    has_parent = (
        subprocess.run(
            ["git", "-C", str(cwd), "rev-parse", "--verify", "--quiet", base], capture_output=True
        ).returncode
        == 0
    )
    if not has_parent:
        # The first in-scope commit is the repository's root commit;
        # diff against git's well-known empty tree instead.
        base = _EMPTY_TREE_HASH
    tip = commits[-1]
    diff = subprocess.run(
        ["git", "-C", str(cwd), "diff", base, tip], capture_output=True, text=True, check=True
    ).stdout
    if len(diff.encode()) > max_bytes:
        truncated = diff.encode()[:max_bytes].decode(errors="ignore")
        return truncated + _TRUNCATION_NOTICE
    return diff


@dataclass(frozen=True)
class ReviewAttempt:
    prepared: PreparedAttempt
    verdict_path: Path
    diff_path: Path


def prepare_review_attempt(
    plan_dir: Path,
    review_node_id: str,
    attempt_index: int,
    task_files: list[Path],
    diff_text: str,
) -> ReviewAttempt:
    """Populate a fresh reviewer attempt dir; returns its key paths."""
    directory = attempt_dir(plan_dir, review_node_id, attempt_index)
    directory.mkdir(parents=True, exist_ok=True)
    hooks_file, signals_path = write_hooks_fragment(directory)

    process_doc = directory / "process.md"
    process_doc.write_text(builtin_data_text("review_task.md"))
    diff_path = directory / DIFF_FILENAME
    diff_path.write_text(diff_text)
    verdict_path = directory / VERDICT_FILENAME

    task_list = ", ".join(str(path.resolve()) for path in task_files)
    prompt = (
        "You are reviewing completed work; do not modify the repository. "
        f"Follow the review process at {process_doc.resolve()}. "
        f"The task file(s) under review: {task_list}. "
        f"The diff under review: {diff_path.resolve()}. "
        f"Write your verdict to {verdict_path.resolve()} using the schema in the process document. "
        "Work autonomously; never wait for user input; when the verdict is written, stop."
    )
    (directory / "prompt.txt").write_text(prompt + "\n")

    prepared = PreparedAttempt(
        attempt_dir=directory,
        hooks_file=hooks_file,
        prompt=prompt,
        signals_path=signals_path,
        process_doc=process_doc,
        context_file=None,
    )
    return ReviewAttempt(prepared=prepared, verdict_path=verdict_path, diff_path=diff_path)

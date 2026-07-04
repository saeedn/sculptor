"""End-of-run Review handoff.

After a fully-successful run, the coordinator hands the feature to the
Review agent: inside Sculptor it spawns a Claude CLI tab and types the
seeded `/sculptor-workflow:review` invocation into it (via the sculpt
CLI, discovered — never imported); standalone it prints the same seed
text for the user to run in a review session. A handoff failure never
crashes the completed run.
"""

import json
import os
import shutil
import subprocess
import time
from collections.abc import Callable
from collections.abc import Mapping
from pathlib import Path

from coordinator.manifest import PlanManifest

# The Review agent runs in a Claude Code tab; its registration accepts
# automated prompts (the coordinator's own deliberately does not).
REVIEW_HARNESS = "Claude CLI"

# A freshly created tab needs its shell + claude to boot before a typed
# prompt lands; retry sends within a bounded window.
_SEND_RETRY_WINDOW_SECONDS = 30.0
_SEND_RETRY_INTERVAL_SECONDS = 3.0
_SCULPT_TIMEOUT_SECONDS = 60.0


def build_review_seed(plan_dir: Path, manifest: PlanManifest) -> str:
    """The seeded review invocation (marker lines only for known values).

    The manifest's optional ``meta`` block wins; without it the
    directory-per-spec layout is assumed: the plan folder's parent holds
    spec.md / architecture.md and its name is the slug.
    """
    plan_dir = plan_dir.resolve()
    parent = plan_dir.parent
    meta = manifest.meta
    slug = meta.slug if meta is not None and meta.slug is not None else parent.name
    if meta is not None and meta.spec is not None:
        spec_path = (plan_dir / meta.spec).resolve()
    else:
        spec_path = parent / "spec.md"
    if meta is not None and meta.architecture is not None:
        architecture_path = (plan_dir / meta.architecture).resolve()
    else:
        architecture_path = parent / "architecture.md"

    lines = ["/sculptor-workflow:review"]
    if slug:
        lines.append(f"Slug: {slug}")
    if spec_path.is_file():
        lines.append(f"Spec path: {spec_path}")
    if architecture_path.is_file():
        lines.append(f"Architecture path: {architecture_path}")
    lines.append(f"Plan folder: {plan_dir}")
    lines.append("Diff range: origin/main...HEAD")
    return "\n".join(lines)


def _print_fallback(seed: str, out: Callable[[str], None]) -> None:
    out("Run the final review by starting a review session with this input:")
    out(seed)


def handoff_review(
    plan_dir: Path,
    manifest: PlanManifest,
    *,
    env: Mapping[str, str] | None = None,
    out: Callable[[str], None] = print,
    sleep: Callable[[float], None] = time.sleep,
    send_retry_window_seconds: float = _SEND_RETRY_WINDOW_SECONDS,
    send_retry_interval_seconds: float = _SEND_RETRY_INTERVAL_SECONDS,
) -> str | None:
    """Spawn the seeded Review agent; returns its id, or None on the printed fallback."""
    seed = build_review_seed(plan_dir, manifest)
    environment = env if env is not None else os.environ
    sculpt_path = shutil.which("sculpt", path=environment.get("PATH"))
    inside_sculptor = (
        sculpt_path is not None
        and bool(environment.get("SCULPT_AGENT_ID"))
        and bool(environment.get("SCULPT_WORKSPACE_ID"))
    )
    if not inside_sculptor:
        _print_fallback(seed, out)
        return None
    assert sculpt_path is not None
    try:
        created = subprocess.run(
            [sculpt_path, "agent", "create", "--harness", REVIEW_HARNESS, "--json"],
            capture_output=True,
            text=True,
            timeout=_SCULPT_TIMEOUT_SECONDS,
        )
        if created.returncode != 0:
            raise RuntimeError(f"sculpt agent create failed: {created.stderr.strip() or created.stdout.strip()}")
        agent_id = json.loads(created.stdout)["id"]
        deadline = time.monotonic() + send_retry_window_seconds
        while True:
            sent = subprocess.run(
                [sculpt_path, "agent", "send", agent_id, seed],
                capture_output=True,
                text=True,
                timeout=_SCULPT_TIMEOUT_SECONDS,
            )
            if sent.returncode == 0:
                out(f"Review agent spawned: {agent_id} — the review continues in that tab.")
                return agent_id
            if time.monotonic() >= deadline:
                raise RuntimeError(f"sculpt agent send kept failing: {sent.stderr.strip() or sent.stdout.strip()}")
            sleep(send_retry_interval_seconds)
    except Exception as e:
        # Never crash a completed run over the handoff.
        out(f"Could not spawn the Review agent ({e}).")
        _print_fallback(seed, out)
        return None

import os
from pathlib import Path

import pytest

from coordinator.manifest import ManifestDefaults
from coordinator.manifest import ManifestMeta
from coordinator.manifest import PhaseSpec
from coordinator.manifest import PlanManifest
from coordinator.manifest import TaskSpec
from coordinator.review_spawn import build_review_seed
from coordinator.review_spawn import handoff_review

FAKE_CREATE_RESPONSE = (
    '{"id": "tsk_review123", "title": "Review", "status": "RUNNING",'
    + ' "workspace_id": "ws_x", "created_at": "2024-01-01T00:00:00Z"}'
)


def make_manifest(meta: ManifestMeta | None = None) -> PlanManifest:
    return PlanManifest(
        version=1,
        meta=meta,
        defaults=ManifestDefaults(worker="w", verification=[]),
        phases=[PhaseSpec(id=1, name="P", tasks=[TaskSpec(id="1.1", file="a.md")])],
    )


def make_feature_layout(tmp_path: Path, with_spec: bool = True, with_architecture: bool = True) -> Path:
    feature = tmp_path / "agent_docs" / "my-feature"
    plan_dir = feature / "plan"
    plan_dir.mkdir(parents=True)
    if with_spec:
        (feature / "spec.md").write_text("# Spec\n")
    if with_architecture:
        (feature / "architecture.md").write_text("# Architecture\n")
    return plan_dir


def test_seed_from_manifest_meta(tmp_path: Path) -> None:
    plan_dir = make_feature_layout(tmp_path)
    meta = ManifestMeta(slug="custom-slug", spec="../spec.md", architecture="../architecture.md")
    seed = build_review_seed(plan_dir, make_manifest(meta))
    lines = seed.splitlines()
    assert lines[0] == "/sculptor-workflow:review"
    assert "Slug: custom-slug" in lines
    assert f"Spec path: {(plan_dir.parent / 'spec.md').resolve()}" in lines
    assert f"Architecture path: {(plan_dir.parent / 'architecture.md').resolve()}" in lines
    assert f"Plan folder: {plan_dir.resolve()}" in lines
    assert lines[-1] == "Diff range: origin/main...HEAD"


def test_seed_derived_from_layout(tmp_path: Path) -> None:
    plan_dir = make_feature_layout(tmp_path)
    seed = build_review_seed(plan_dir, make_manifest())
    assert "Slug: my-feature" in seed
    assert f"Spec path: {(plan_dir.parent / 'spec.md').resolve()}" in seed


def test_seed_omits_missing_files(tmp_path: Path) -> None:
    plan_dir = make_feature_layout(tmp_path, with_spec=False, with_architecture=False)
    seed = build_review_seed(plan_dir, make_manifest())
    assert "Spec path:" not in seed
    assert "Architecture path:" not in seed
    assert f"Plan folder: {plan_dir.resolve()}" in seed
    assert "Diff range: origin/main...HEAD" in seed


def make_fake_sculpt(tmp_path: Path, create_exit: int = 0, send_exit: int = 0) -> tuple[Path, Path]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    log_path = tmp_path / "sculpt_calls.log"
    script = bin_dir / "sculpt"
    script.write_text(
        "#!/bin/sh\n"
        + f'echo "$@" >> "{log_path}"\n'
        + 'if [ "$1" = "agent" ] && [ "$2" = "create" ]; then\n'
        + f"  echo '{FAKE_CREATE_RESPONSE}'\n"
        + f"  exit {create_exit}\n"
        + "fi\n"
        + 'if [ "$1" = "agent" ] && [ "$2" = "send" ]; then\n'
        + f"  exit {send_exit}\n"
        + "fi\n"
        + "exit 0\n"
    )
    script.chmod(0o755)
    return bin_dir, log_path


def sculptor_env(bin_dir: Path) -> dict[str, str]:
    return {
        "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
        "SCULPT_AGENT_ID": "tsk_coordinator",
        "SCULPT_WORKSPACE_ID": "ws_test",
    }


def test_handoff_outside_sculptor_prints_fallback(tmp_path: Path) -> None:
    plan_dir = make_feature_layout(tmp_path)
    printed: list[str] = []
    agent_id = handoff_review(plan_dir, make_manifest(), env={}, out=printed.append)
    assert agent_id is None
    assert any("/sculptor-workflow:review" in line for line in printed)


def test_handoff_spawns_and_sends_inside_sculptor(tmp_path: Path) -> None:
    plan_dir = make_feature_layout(tmp_path)
    bin_dir, log_path = make_fake_sculpt(tmp_path)
    printed: list[str] = []
    agent_id = handoff_review(plan_dir, make_manifest(), env=sculptor_env(bin_dir), out=printed.append)
    assert agent_id == "tsk_review123"
    log = log_path.read_text()
    calls = log.splitlines()
    assert calls[0] == "agent create --harness Claude CLI --json"
    # The multiline seed is ONE send argument; echo spreads it over lines.
    assert calls[1] == "agent send tsk_review123 /sculptor-workflow:review"
    assert "Plan folder:" in log
    assert "Diff range: origin/main...HEAD" in log
    assert any("tsk_review123" in line for line in printed)


def test_handoff_create_failure_falls_back(tmp_path: Path) -> None:
    plan_dir = make_feature_layout(tmp_path)
    bin_dir, log_path = make_fake_sculpt(tmp_path, create_exit=1)
    printed: list[str] = []
    agent_id = handoff_review(plan_dir, make_manifest(), env=sculptor_env(bin_dir), out=printed.append)
    assert agent_id is None
    assert any("Could not spawn the Review agent" in line for line in printed)
    assert any("/sculptor-workflow:review" in line for line in printed)
    # No send was attempted after the failed create.
    assert all(not line.startswith("agent send") for line in log_path.read_text().splitlines())


def test_handoff_send_failure_retries_then_falls_back(tmp_path: Path) -> None:
    plan_dir = make_feature_layout(tmp_path)
    bin_dir, log_path = make_fake_sculpt(tmp_path, send_exit=1)
    printed: list[str] = []
    sleeps: list[float] = []
    agent_id = handoff_review(
        plan_dir,
        make_manifest(),
        env=sculptor_env(bin_dir),
        out=printed.append,
        sleep=sleeps.append,
        send_retry_window_seconds=0.0,
        send_retry_interval_seconds=0.0,
    )
    assert agent_id is None
    assert any("Could not spawn the Review agent" in line for line in printed)
    sends = [line for line in log_path.read_text().splitlines() if line.startswith("agent send")]
    assert len(sends) >= 1


@pytest.mark.parametrize("missing", ["SCULPT_AGENT_ID", "SCULPT_WORKSPACE_ID"])
def test_handoff_requires_full_sculptor_env(tmp_path: Path, missing: str) -> None:
    plan_dir = make_feature_layout(tmp_path)
    bin_dir, log_path = make_fake_sculpt(tmp_path)
    env = sculptor_env(bin_dir)
    del env[missing]
    printed: list[str] = []
    assert handoff_review(plan_dir, make_manifest(), env=env, out=printed.append) is None
    assert not log_path.exists()

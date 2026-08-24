from pathlib import Path

import pytest
from loguru import logger
from pydantic import ValidationError

from coordinator.manifest import ManifestDefaults
from coordinator.manifest import ManifestError
from coordinator.manifest import PhaseSpec
from coordinator.manifest import PlanManifest
from coordinator.manifest import TaskSpec
from coordinator.registrations import WorkerRegistration
from coordinator.registrations import load_registrations
from coordinator.registrations import render
from coordinator.registrations import resolve_worker

BUILTIN_NAMES = {"claude-sonnet", "claude-opus", "claude-fable"}


@pytest.fixture(autouse=True)
def isolated_user_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    config_home = tmp_path / "xdg-config"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))
    return config_home


def write_registration(directory: Path, name: str, display_name: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{name}.yaml").write_text(f'display_name: {display_name}\ncommand: ["worker", "{{prompt}}"]\n')


def test_builtins_load(tmp_path: Path) -> None:
    registrations = load_registrations(tmp_path)
    assert BUILTIN_NAMES <= set(registrations)
    for name in BUILTIN_NAMES:
        assert "-p" in registrations[name].command
        assert "--dangerously-skip-permissions" in registrations[name].command
    # A default plan can escalate: the registrations differ only by model.
    assert registrations["claude-sonnet"].model == "sonnet"
    assert registrations["claude-opus"].model == "opus"
    assert registrations["claude-fable"].model == "fable"


def test_claude_renders_to_valid_argv(tmp_path: Path) -> None:
    registrations = load_registrations(tmp_path)
    argv, env = render(
        registrations["claude-opus"],
        prompt="do the thing",
        settings_file="/attempt/hooks.json",
        attempt_dir="/attempt",
        cwd="/repo",
    )
    # The model is pinned, never left to the harness default.
    assert argv == [
        "claude",
        "-p",
        "--dangerously-skip-permissions",
        "--model",
        "opus",
        "--settings",
        "/attempt/hooks.json",
        "do the thing",
    ]
    assert env == {}


def test_render_handles_embedded_placeholders_and_literal_braces() -> None:
    registration = WorkerRegistration(
        name="w",
        display_name="W",
        command=["worker", "--settings={settings_file}", "{prompt}"],
        env={"WORKDIR": "{cwd}"},
    )
    argv, env = render(
        registration,
        prompt="prompt with {cwd} braces",
        settings_file="/s.json",
        attempt_dir="/a",
        cwd="/repo",
    )
    # Embedded placeholders render; braces inside substituted values are
    # not re-expanded.
    assert argv == ["worker", "--settings=/s.json", "prompt with {cwd} braces"]
    assert env == {"WORKDIR": "/repo"}


def test_model_placeholder_renders() -> None:
    registration = WorkerRegistration(
        name="w",
        display_name="W",
        command=["worker", "--model", "{model}", "{prompt}"],
        model="opus",
    )
    argv, _ = render(registration, prompt="p", settings_file="/s", attempt_dir="/a", cwd="/c")
    assert argv == ["worker", "--model", "opus", "p"]


def test_unknown_placeholder_rejected() -> None:
    with pytest.raises(ValidationError) as exc_info:
        WorkerRegistration(name="w", display_name="W", command=["worker", "{prompt}", "{session_id}"])
    assert "{session_id}" in str(exc_info.value)


def test_unknown_placeholder_in_env_rejected() -> None:
    with pytest.raises(ValidationError):
        WorkerRegistration(name="w", display_name="W", command=["worker", "{prompt}"], env={"X": "{typo}"})


def test_missing_prompt_rejected() -> None:
    with pytest.raises(ValidationError) as exc_info:
        WorkerRegistration(name="w", display_name="W", command=["worker"])
    assert "{prompt}" in str(exc_info.value)


def test_double_prompt_rejected() -> None:
    with pytest.raises(ValidationError):
        WorkerRegistration(name="w", display_name="W", command=["worker", "{prompt}", "{prompt}"])


def test_legacy_mode_key_is_ignored(tmp_path: Path) -> None:
    # Workers are headless-only; a `mode:` left over in someone's own
    # registration must not break their run.
    workers = tmp_path / ".sculptor" / "workers"
    workers.mkdir(parents=True)
    (workers / "legacy.yaml").write_text('display_name: Legacy\nmode: print\ncommand: ["worker", "{prompt}"]\n')
    assert load_registrations(tmp_path)["legacy"].display_name == "Legacy"


def test_model_placeholder_without_model_rejected() -> None:
    with pytest.raises(ValidationError):
        WorkerRegistration(name="w", display_name="W", command=["worker", "{model}", "{prompt}"])


def test_layering_repo_shadows_user_shadows_builtin(tmp_path: Path, isolated_user_config: Path) -> None:
    repo_root = tmp_path / "repo"
    write_registration(isolated_user_config / "coordinator" / "workers", "claude-opus", "user-level")
    write_registration(isolated_user_config / "coordinator" / "workers", "user-only", "user-only")
    write_registration(repo_root / ".sculptor" / "workers", "claude-opus", "repo-level")
    registrations = load_registrations(repo_root)
    assert registrations["claude-opus"].display_name == "repo-level"
    assert registrations["user-only"].display_name == "user-only"


def test_broken_files_collected_into_one_error(tmp_path: Path) -> None:
    workers = tmp_path / ".sculptor" / "workers"
    workers.mkdir(parents=True)
    (workers / "bad-yaml.yaml").write_text("command: [unclosed\n")
    (workers / "bad-schema.yaml").write_text('display_name: X\ncommand: ["worker"]\n')
    with pytest.raises(ManifestError) as exc_info:
        load_registrations(tmp_path)
    assert "bad-yaml.yaml" in str(exc_info.value)
    assert "bad-schema.yaml" in str(exc_info.value)


def make_manifest(worker: str, task_worker: str | None = None) -> tuple[PlanManifest, TaskSpec]:
    task = TaskSpec(id="1.1", file="a.md", worker=task_worker)
    manifest = PlanManifest(
        version=1,
        defaults=ManifestDefaults(worker=worker, verification=[]),
        phases=[PhaseSpec(id=1, name="P", tasks=[task])],
    )
    return manifest, task


def test_resolve_worker_prefers_task_override(tmp_path: Path) -> None:
    write_registration(tmp_path / ".sculptor" / "workers", "stronger", "Stronger")
    registrations = load_registrations(tmp_path)
    manifest, task = make_manifest("claude-sonnet", task_worker="stronger")
    assert resolve_worker(manifest, task, registrations) == "stronger"


def test_resolve_worker_falls_back_to_default(tmp_path: Path) -> None:
    registrations = load_registrations(tmp_path)
    manifest, task = make_manifest("claude-sonnet")
    assert resolve_worker(manifest, task, registrations) == "claude-sonnet"


def test_resolve_worker_unknown_name_raises(tmp_path: Path) -> None:
    registrations = load_registrations(tmp_path)
    manifest, task = make_manifest("no-such-worker")
    with pytest.raises(ManifestError) as exc_info:
        resolve_worker(manifest, task, registrations)
    assert "task 1.1" in str(exc_info.value)
    assert "no-such-worker" in str(exc_info.value)


def test_stale_mode_key_loads_but_warns(tmp_path: Path) -> None:
    # Registrations written before the launcher went headless-only still
    # work; `mode: interactive` just stopped meaning anything, and a
    # silent change of behaviour is worse than a noisy one.
    workers = tmp_path / ".sculptor" / "workers"
    workers.mkdir(parents=True)
    (workers / "legacy.yaml").write_text('display_name: Legacy\nmode: interactive\ncommand: ["worker", "{prompt}"]\n')
    warnings: list[str] = []
    handler_id = logger.add(lambda message: warnings.append(message), level="WARNING")
    try:
        registrations = load_registrations(tmp_path)
    finally:
        logger.remove(handler_id)
    assert registrations["legacy"].display_name == "Legacy"
    assert any("mode: interactive" in warning for warning in warnings)

"""Sculptor tab-status signaling through the sculpt CLI.

The coordinator stays fully standalone: sculpt is DISCOVERED at runtime
(never imported) and used only when both `sculpt` is on PATH and
`SCULPT_AGENT_ID` is set — i.e. when running inside a Sculptor agent
shell. Outside Sculptor every signal is a silent no-op and behavior is
otherwise identical.

Signal failures (backend down, sculpt broken) are logged to stderr and
IGNORED — signaling must never break a run.
"""

import os
import shutil
import subprocess
import sys
from collections.abc import Mapping

_SIGNAL_TIMEOUT_SECONDS = 10.0


class NullSignaler:
    """The outside-Sculptor signaler: every signal is a no-op."""

    def busy(self) -> None:
        pass

    def idle(self) -> None:
        pass

    def waiting(self) -> None:
        pass

    def files_changed(self) -> None:
        pass

    def session_id(self, run_id: str) -> None:
        pass


class SculptSignaler:
    """Signals tab status via `sculpt signal ...` subprocess calls."""

    def __init__(self, sculpt_path: str) -> None:
        self.sculpt_path = sculpt_path

    def _signal(self, *args: str) -> None:
        try:
            subprocess.run(
                [self.sculpt_path, "signal", *args],
                capture_output=True,
                timeout=_SIGNAL_TIMEOUT_SECONDS,
                check=True,
            )
        except Exception as e:
            print(f"warning: sculpt signal {' '.join(args)} failed: {e}", file=sys.stderr)

    def busy(self) -> None:
        self._signal("busy")

    def idle(self) -> None:
        self._signal("idle")

    def waiting(self) -> None:
        self._signal("waiting")

    def files_changed(self) -> None:
        self._signal("files-changed")

    def session_id(self, run_id: str) -> None:
        self._signal("session-id", run_id)


Signaler = SculptSignaler | NullSignaler


def detect_signaler(env: Mapping[str, str] | None = None) -> Signaler:
    environment = env if env is not None else os.environ
    sculpt_path = shutil.which("sculpt", path=environment.get("PATH"))
    if sculpt_path is None or not environment.get("SCULPT_AGENT_ID"):
        return NullSignaler()
    return SculptSignaler(sculpt_path)

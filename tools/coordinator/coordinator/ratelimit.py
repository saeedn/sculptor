"""Rate-limit classification from worker attempt artifacts.

A rate-limited attempt must not burn retry budget: the run pauses with
the resume time surfaced instead. Classification reads FILES — the
transcript tail, the captured stderr, and the last assistant message —
never the screen.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from coordinator.scheduler import AttemptResult

_TAIL_BYTES = 64 * 1024

# Case-insensitive substrings that mark a rate-limited attempt. Exact
# strings drift across Claude Code versions — extend this list as new
# phrasings show up in the wild.
RATE_LIMIT_MARKERS = (
    "rate limit",
    "rate-limit",
    "usage limit reached",
    "you've reached your usage limit",
    "429",
    "overloaded_error",
)

# "resets at 6pm", "resets at 2026-07-03T18:00:00Z", "reset at ..." —
# capture the remainder of the phrase as the resume hint.
_RESET_PATTERN = re.compile(r"resets? (?:at|in) ([^\n\"\\]+)", re.IGNORECASE)
_ISO_TIMESTAMP_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}T[0-9:]{5,8}(?:Z|[+-]\d{2}:?\d{2})?")


@dataclass(frozen=True)
class RateLimit:
    resume_hint: str | None


def _tail(path: Path) -> str:
    try:
        data = path.read_bytes()
    except OSError:
        return ""
    return data[-_TAIL_BYTES:].decode(errors="replace")


def classify_attempt(result: "AttemptResult", attempt_dir: Path | None = None) -> RateLimit | None:
    """``RateLimit`` when the attempt's artifacts show a rate-limit marker, else None."""
    texts: list[str] = []
    if result.transcript_path is not None:
        transcript = Path(result.transcript_path)
        if transcript.is_file():
            texts.append(_tail(transcript))
    if result.last_assistant_message:
        texts.append(result.last_assistant_message)
    if attempt_dir is not None:
        stderr_log = attempt_dir / "stderr.log"
        if stderr_log.is_file():
            texts.append(_tail(stderr_log))
    combined = "\n".join(texts)
    lowered = combined.lower()
    if not any(marker in lowered for marker in RATE_LIMIT_MARKERS):
        return None
    reset_match = _RESET_PATTERN.search(combined)
    if reset_match is not None:
        return RateLimit(resume_hint=f"resets at {reset_match.group(1).strip()}")
    iso_match = _ISO_TIMESTAMP_PATTERN.search(combined)
    if iso_match is not None:
        return RateLimit(resume_hint=f"resets around {iso_match.group(0)}")
    return RateLimit(resume_hint=None)

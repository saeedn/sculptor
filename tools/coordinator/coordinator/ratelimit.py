"""Rate-limit classification from worker attempt artifacts.

A rate-limited attempt must not burn retry budget: the run pauses with
the resume time surfaced instead. Classification reads FILES — the
transcript tail's non-content entries and the captured process output —
never the screen.
"""

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel
from pydantic import ConfigDict

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
    "overloaded_error",
)

# A bare "429" is not a marker: those digits occur inside token counts
# ("cache_read_input_tokens":142990), timestamps, and hashes, and one
# such match silently converts an unrelated failure into a rate-limit
# pause. Require the structure of an actual HTTP status instead.
_HTTP_429_PATTERN = re.compile(
    r"\"status(?:_?code)?\"\s*:\s*429\b"
    r"|\bstatus(?:\s+code)?\s*[:=]\s*429\b"
    r"|\bhttp(?:/[\d.]+)?\s+429\b"
    r"|\b429\s+too\s+many\s+requests\b",
    re.IGNORECASE,
)

# "resets at 6pm", "resets at 2026-07-03T18:00:00Z", "reset at ..." —
# capture the remainder of the phrase as the resume hint.
_RESET_PATTERN = re.compile(r"resets? (?:at|in) ([^\n\"\\]+)", re.IGNORECASE)
_ISO_TIMESTAMP_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}T[0-9:]{5,8}(?:Z|[+-]\d{2}:?\d{2})?")


class RateLimit(BaseModel):
    model_config = ConfigDict(frozen=True)

    resume_hint: str | None


def _tail(path: Path) -> str:
    """The last ``_TAIL_BYTES`` of a file, starting at a line boundary.

    The cut lands mid-line in general, and a partial JSONL line would
    fail to parse and therefore escape the content filter below — so the
    truncated first line is dropped whenever the tail is not the whole
    file.
    """
    try:
        data = path.read_bytes()
    except OSError:
        return ""
    if len(data) <= _TAIL_BYTES:
        return data.decode(errors="replace")
    tail = data[-_TAIL_BYTES:]
    newline = tail.find(b"\n")
    if newline == -1:
        # One enormous line spans the whole tail; nothing survives the cut.
        return ""
    return tail[newline + 1 :].decode(errors="replace")


def _transcript_error_text(path: Path) -> str:
    """The transcript tail with conversation content stripped.

    A transcript is JSONL of conversation entries, and user/assistant
    content legitimately discusses rate limits (a task ABOUT rate
    limiting must not pause the run on every attempt). A real rate limit
    surfaces in error/system entries, so only non-content lines are
    scanned; lines that don't parse as JSON are scanned as-is.
    """
    lines: list[str] = []
    for line in _tail(path).splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            entry = json.loads(stripped)
        except ValueError:
            lines.append(stripped)
            continue
        if isinstance(entry, dict) and entry.get("type") in ("user", "assistant"):
            continue
        lines.append(stripped)
    return "\n".join(lines)


def classify_attempt(result: "AttemptResult", attempt_dir: Path | None = None) -> RateLimit | None:
    """``RateLimit`` when the attempt's artifacts show a rate-limit marker, else None.

    Scans error surfaces only — the transcript's non-content entries and
    the captured process output — never the conversation itself.
    """
    texts: list[str] = []
    if result.transcript_path is not None:
        transcript = Path(result.transcript_path)
        if transcript.is_file():
            texts.append(_transcript_error_text(transcript))
    if attempt_dir is not None:
        for log_name in ("stderr.log", "stdout.log"):
            log = attempt_dir / log_name
            if log.is_file():
                texts.append(_tail(log))
    combined = "\n".join(texts)
    lowered = combined.lower()
    if not any(marker in lowered for marker in RATE_LIMIT_MARKERS) and _HTTP_429_PATTERN.search(combined) is None:
        return None
    reset_match = _RESET_PATTERN.search(combined)
    if reset_match is not None:
        return RateLimit(resume_hint=f"resets at {reset_match.group(1).strip()}")
    iso_match = _ISO_TIMESTAMP_PATTERN.search(combined)
    if iso_match is not None:
        return RateLimit(resume_hint=f"resets around {iso_match.group(0)}")
    return RateLimit(resume_hint=None)

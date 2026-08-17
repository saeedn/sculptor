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

# Case-insensitive substrings specific enough to mean a rate limit
# wherever they appear, including in text the model itself wrote. Exact
# strings drift across Claude Code versions — extend these lists as new
# phrasings show up in the wild.
UNAMBIGUOUS_RATE_LIMIT_MARKERS = (
    "usage limit reached",
    "you've reached your usage limit",
    "overloaded_error",
)

# The generic phrasings on top. These are ordinary English a worker
# writes while doing ordinary work, so they count only on surfaces the
# model does not author.
RATE_LIMIT_MARKERS = UNAMBIGUOUS_RATE_LIMIT_MARKERS + (
    "rate limit",
    "rate-limit",
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


def _tail(path: Path, *, whole_lines: bool = False) -> str:
    """The last ``_TAIL_BYTES`` of a file.

    ``whole_lines`` drops the leading fragment the cut leaves behind. Ask
    for it when the caller parses the tail line by line — a partial JSONL
    line fails to parse and would escape the content filter below. Plain
    logs are not line-structured, so they keep the raw tail: dropping to
    the first newline there can discard the whole window.
    """
    try:
        data = path.read_bytes()
    except OSError:
        return ""
    if len(data) <= _TAIL_BYTES:
        return data.decode(errors="replace")
    tail = data[-_TAIL_BYTES:]
    if not whole_lines:
        return tail.decode(errors="replace")
    newline = tail.find(b"\n")
    if newline == -1:
        # One enormous line spans the whole tail; no complete line survives.
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
    for line in _tail(path, whole_lines=True).splitlines():
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


def _matches(text: str, markers: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in markers) or _HTTP_429_PATTERN.search(text) is not None


def classify_attempt(result: "AttemptResult", attempt_dir: Path | None = None) -> RateLimit | None:
    """``RateLimit`` when the attempt's artifacts show a rate-limit marker, else None.

    Two surfaces, two bars. The transcript's non-content entries and
    ``stderr.log`` are the harness talking, so every marker counts there.
    ``stdout.log`` under ``claude -p`` is the worker's own final message —
    conversation, held to the unambiguous markers only, or a task about
    rate limiting would pause its own run on every attempt.
    """
    error_texts: list[str] = []
    content_texts: list[str] = []
    if result.transcript_path is not None:
        transcript = Path(result.transcript_path)
        if transcript.is_file():
            error_texts.append(_transcript_error_text(transcript))
    if attempt_dir is not None:
        for log_name, texts in (("stderr.log", error_texts), ("stdout.log", content_texts)):
            log = attempt_dir / log_name
            if log.is_file():
                texts.append(_tail(log))
    if not _matches("\n".join(error_texts), RATE_LIMIT_MARKERS) and not _matches(
        "\n".join(content_texts), UNAMBIGUOUS_RATE_LIMIT_MARKERS
    ):
        return None
    combined = "\n".join(error_texts + content_texts)
    reset_match = _RESET_PATTERN.search(combined)
    if reset_match is not None:
        return RateLimit(resume_hint=f"resets at {reset_match.group(1).strip()}")
    iso_match = _ISO_TIMESTAMP_PATTERN.search(combined)
    if iso_match is not None:
        return RateLimit(resume_hint=f"resets around {iso_match.group(0)}")
    return RateLimit(resume_hint=None)

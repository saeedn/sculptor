import json
from pathlib import Path

import pytest

from coordinator.ratelimit import RATE_LIMIT_MARKERS
from coordinator.ratelimit import classify_attempt
from coordinator.scheduler import AttemptResult


def result_with_transcript(tmp_path: Path, text: str) -> AttemptResult:
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text(text)
    return AttemptResult(is_ok=False, status="exited-without-stop", transcript_path=str(transcript))


@pytest.mark.parametrize("marker", RATE_LIMIT_MARKERS)
def test_each_marker_classifies(tmp_path: Path, marker: str) -> None:
    result = result_with_transcript(tmp_path, f"some output\nError: {marker} hit\n")
    assert classify_attempt(result) is not None


def test_clean_transcript_is_not_rate_limited(tmp_path: Path) -> None:
    result = result_with_transcript(tmp_path, "all good, task finished normally\n")
    assert classify_attempt(result) is None


def test_marker_case_insensitive(tmp_path: Path) -> None:
    result = result_with_transcript(tmp_path, "RATE LIMIT exceeded\n")
    assert classify_attempt(result) is not None


def test_last_assistant_message_is_not_scanned() -> None:
    # Assistant content is conversation, not an error surface — a worker
    # merely TALKING about rate limits must not pause the run.
    result = AttemptResult(is_ok=False, status="completed", last_assistant_message="I hit a rate limit, sorry")
    assert classify_attempt(result) is None


def test_conversation_content_about_rate_limits_is_ignored(tmp_path: Path) -> None:
    lines = [
        json.dumps({"type": "user", "message": "implement rate limit handling for HTTP 429"}),
        json.dumps({"type": "assistant", "message": "added the rate-limit retry logic"}),
    ]
    result = result_with_transcript(tmp_path, "\n".join(lines) + "\n")
    assert classify_attempt(result) is None


def test_transcript_error_entry_classifies(tmp_path: Path) -> None:
    line = json.dumps({"type": "system", "subtype": "error", "message": "API Error: 429 rate limit"})
    result = result_with_transcript(tmp_path, line + "\n")
    assert classify_attempt(result) is not None


def test_marker_in_stdout_log(tmp_path: Path) -> None:
    attempt_dir = tmp_path / "attempt"
    attempt_dir.mkdir()
    (attempt_dir / "stdout.log").write_text("Claude usage limit reached\n")
    result = AttemptResult(is_ok=False, status="exited-without-stop")
    assert classify_attempt(result, attempt_dir) is not None


def test_marker_in_stderr_log(tmp_path: Path) -> None:
    attempt_dir = tmp_path / "attempt"
    attempt_dir.mkdir()
    (attempt_dir / "stderr.log").write_text("HTTP 429 from api.anthropic.com\n")
    result = AttemptResult(is_ok=False, status="exited-without-stop")
    assert classify_attempt(result, attempt_dir) is not None


def test_no_artifacts_is_not_rate_limited() -> None:
    result = AttemptResult(is_ok=False, status="timeout")
    assert classify_attempt(result) is None


def test_missing_transcript_file_ignored() -> None:
    result = AttemptResult(is_ok=False, status="exited-without-stop", transcript_path="/nonexistent/transcript.jsonl")
    assert classify_attempt(result) is None


def test_reset_time_extracted_from_phrase(tmp_path: Path) -> None:
    result = result_with_transcript(tmp_path, "You've reached your usage limit. resets at 6pm (America/Chicago)\n")
    rate_limit = classify_attempt(result)
    assert rate_limit is not None
    assert rate_limit.resume_hint is not None
    assert "6pm" in rate_limit.resume_hint


def test_reset_time_extracted_from_iso_timestamp(tmp_path: Path) -> None:
    result = result_with_transcript(tmp_path, "overloaded_error until 2026-07-03T18:00:00Z\n")
    rate_limit = classify_attempt(result)
    assert rate_limit is not None
    assert rate_limit.resume_hint is not None
    assert "2026-07-03T18:00:00Z" in rate_limit.resume_hint


def test_no_reset_time_gives_none_hint(tmp_path: Path) -> None:
    result = result_with_transcript(tmp_path, "usage limit reached\n")
    rate_limit = classify_attempt(result)
    assert rate_limit is not None
    assert rate_limit.resume_hint is None


@pytest.mark.parametrize(
    "text",
    [
        '"cache_read_input_tokens":142990',
        '"output_tokens":4290',
        "commit 429fa17b3c",
        "elapsed 14:29:03",
    ],
)
def test_digits_containing_429_are_not_a_rate_limit(tmp_path: Path, text: str) -> None:
    # A bare "429" substring occurs constantly in token counts, hashes,
    # and timestamps; only an HTTP status shape counts.
    attempt_dir = tmp_path / "attempt"
    attempt_dir.mkdir()
    (attempt_dir / "stdout.log").write_text(text + "\n")
    result = AttemptResult(is_ok=False, status="timeout")
    assert classify_attempt(result, attempt_dir) is None


@pytest.mark.parametrize(
    "text",
    ['{"status":429}', '{"status_code": 429}', "status: 429", "HTTP/1.1 429", "429 Too Many Requests"],
)
def test_http_429_shapes_classify(tmp_path: Path, text: str) -> None:
    attempt_dir = tmp_path / "attempt"
    attempt_dir.mkdir()
    (attempt_dir / "stderr.log").write_text(text + "\n")
    result = AttemptResult(is_ok=False, status="exited-without-stop")
    assert classify_attempt(result, attempt_dir) is not None


def test_transcript_tail_never_scans_a_truncated_conversation_line(tmp_path: Path) -> None:
    # The 64KiB tail cuts mid-line. A partial assistant entry does not
    # parse as JSON, and scanning it raw would defeat the content filter
    # entirely — a task ABOUT rate limiting would pause its own run.
    padding = json.dumps({"type": "assistant", "message": "x" * 200}) + "\n"
    long_assistant_line = json.dumps(
        {"type": "assistant", "message": "we must handle rate limit errors", "blob": "y" * 70_000}
    )
    text = padding * 20 + long_assistant_line + "\n" + json.dumps({"type": "user", "message": "ok"}) + "\n"
    result = result_with_transcript(tmp_path, text)
    assert classify_attempt(result) is None


def test_error_entry_after_a_truncated_line_still_classifies(tmp_path: Path) -> None:
    # Dropping the partial first line must not blind the scan to the
    # real error surfaces that follow it.
    long_line = json.dumps({"type": "assistant", "message": "working", "blob": "y" * 70_000})
    error_line = json.dumps({"type": "system", "subtype": "error", "message": "usage limit reached"})
    result = result_with_transcript(tmp_path, long_line + "\n" + error_line + "\n")
    assert classify_attempt(result) is not None

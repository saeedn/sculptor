"""Append one Claude Code hook event to a signals.jsonl file.

Usage (as a hook command): ``python3 append_signal.py <Event> <signals_path>``.
Reads the hook payload JSON from stdin and appends
``{"event": <Event>, "ts": <epoch>, "payload": <stdin JSON or null>}``
as one JSONL line. Tolerates empty or non-JSON stdin and ALWAYS exits 0 —
a failing hook must never break the worker session.

Stdlib-only: this file is copied into each attempt directory and run by
whatever ``python3`` is on the worker's PATH.
"""

import json
import sys
import time


def main() -> None:
    try:
        event = sys.argv[1] if len(sys.argv) > 1 else "unknown"
        signals_path = sys.argv[2] if len(sys.argv) > 2 else None
        raw = sys.stdin.read()
        try:
            payload = json.loads(raw) if raw.strip() else None
        except ValueError:
            payload = None
        if signals_path is not None:
            line = json.dumps({"event": event, "ts": time.time(), "payload": payload})
            with open(signals_path, "a") as f:
                f.write(line + "\n")
    except Exception:
        pass
    sys.exit(0)


if __name__ == "__main__":
    main()

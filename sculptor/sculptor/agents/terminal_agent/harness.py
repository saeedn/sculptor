"""The terminal harness — the `Harness` for terminal agents.

Terminal agents have no chat surface at all: their main panel is a PTY
terminal and Sculptor never parses their output. There is no message
stream, so every capability — including `supports_chat_interface`, the
coarse main-panel switch — is uniformly false.

Terminal configs are dispatched to the dedicated terminal task handler.
"""

from __future__ import annotations

from sculptor.interfaces.agents.harness import Harness


class TerminalHarness(Harness):
    name: str = "terminal"

    # capabilities() inherits the base all-False set: terminal agents have no
    # message stream, so no chat-derived affordance applies.


TERMINAL_HARNESS: TerminalHarness = TerminalHarness()

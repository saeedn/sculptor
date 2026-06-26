"""The harness-agnostic seam — the interface a harness implements.

A `Harness` is the boundary between Sculptor's generic agent layer and a
specific agent-process implementation. The base interface carries only
what every harness-agnostic consumer reads polymorphically:

- *minimum* — `name`.
- *capability* — two coexisting shapes (PHASE_5_NORTH_STAR §2):
  bool-field capabilities live on `HarnessCapabilities` and are reached
  via `Harness.capabilities()`; gated methods stay on the ABC with
  trivial-answer defaults for protocol-level per-call questions no
  bool can express.
- *polymorphic helpers* — `get_jsonl_path_for_working_directory`, which
  returns `None` by default; harnesses with an on-disk session layout
  override it.

Concrete-harness addresses (binary key, session-directory name, MCP
identifiers, lifecycle-hook callback id, system-prompt content, etc.) are
*not* on the base — they live on the concrete harness that owns them.
Claude-side code (`ClaudeProcessManager`, `BtwProcessManager`,
`ClaudeOutputProcessor`, `SculptorMcpServer`, `process_manager_utils`)
holds a `ClaudeCodeHarness` reference and reads those members directly.

Agent construction lives on the registry (`harness_registry.py`), which
owns each harness↔agent factory pair. With the registry owning
construction, the original harness↔agent import cycle does not exist,
and `ClaudeCodeSDKAgent` may declare its `harness` field as
`ClaudeCodeHarness`. See architecture §1.1, §1.5.
"""

from __future__ import annotations

import abc
from pathlib import Path

from pydantic import BaseModel

from sculptor.foundation.pydantic_serialization import SerializableModel


class HarnessCapabilities(SerializableModel):
    """Coarse-grained, bool-typed capabilities a harness advertises.

    Read by backend feature gates and by the frontend (via the generated
    TypeScript twin). Populated truthfully by each harness through
    `Harness.capabilities()`. PHASE_5_NORTH_STAR §2 names this the
    bool-field shape of the capability region.

    Fields have **no Python defaults** — every constructor must list every
    field. When a new capability lands, pydantic validation forces an edit
    at every constructor site (the base `Harness.capabilities()` body,
    every concrete harness's override, every hand-built test fixture), so
    the harness↔capability matrix is grep-complete: `grep <field>` finds
    every harness's stance.

    `supports_context_reset` and `supports_compaction` are distinct: context
    reset is the `/clear` path that discards the session; compaction summarizes
    the session in place at a threshold. They gate different surfaces.

    `supports_chat_interface` is the coarse main-panel switch (chat interface
    vs terminal panel), distinct from the per-affordance bools below it.
    """

    supports_chat_interface: bool
    supports_interactive_backchannel: bool
    supports_skills: bool
    supports_sub_agents: bool
    supports_image_input: bool
    supports_fast_mode: bool
    supports_context_reset: bool
    supports_compaction: bool
    supports_background_tasks: bool
    supports_session_resume: bool
    supports_tool_use_rendering: bool
    supports_file_attachments: bool
    supports_interruption: bool
    supports_file_references: bool


class Harness(BaseModel, abc.ABC):
    """The harness-agnostic seam — see this module's docstring and architecture.md §1.1."""

    name: str

    def capabilities(self) -> HarnessCapabilities:
        """The harness's typed bool-capability set.

        Intentionally not a `staticmethod` — later phases may have the
        answer depend on instance state (e.g. a per-harness config flag
        could flip a capability false). The base returns the
        all-`False` set explicitly; concrete harnesses override
        truthfully.
        """
        return HarnessCapabilities(
            supports_chat_interface=False,
            supports_interactive_backchannel=False,
            supports_skills=False,
            supports_sub_agents=False,
            supports_image_input=False,
            supports_fast_mode=False,
            supports_context_reset=False,
            supports_compaction=False,
            supports_background_tasks=False,
            supports_session_resume=False,
            supports_tool_use_rendering=False,
            supports_file_attachments=False,
            supports_interruption=False,
            supports_file_references=False,
        )

    def get_jsonl_path_for_working_directory(self, home: Path, working_directory: Path) -> Path | None:
        """Return the per-session JSONL directory the harness uses for a
        given (home, working_directory) pair, or `None` when the harness has
        no on-disk session layout.

        Resolved polymorphically by harness-agnostic callers that hold a
        host-side working directory (e.g. the web diagnostics endpoint).
        """
        return None

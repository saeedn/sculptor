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

    Read by the frontend (via the generated TypeScript twin) and populated by
    each harness through `Harness.capabilities()`. The many rich-chat
    capabilities were removed with the chat surface; `supports_skills` is the
    one that survives (the skills panel reads it).
    """

    supports_skills: bool


class Harness(BaseModel, abc.ABC):
    """The harness-agnostic seam — see this module's docstring and architecture.md §1.1."""

    name: str

    def capabilities(self) -> HarnessCapabilities:
        """The harness's typed bool-capability set. The base returns the
        all-`False` set; concrete harnesses override truthfully.
        """
        return HarnessCapabilities(supports_skills=False)

    def get_jsonl_path_for_working_directory(self, home: Path, working_directory: Path) -> Path | None:
        """Return the per-session JSONL directory the harness uses for a
        given (home, working_directory) pair, or `None` when the harness has
        no on-disk session layout.

        Resolved polymorphically by harness-agnostic callers that hold a
        host-side working directory (e.g. the web diagnostics endpoint).
        """
        return None

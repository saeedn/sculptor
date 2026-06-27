from __future__ import annotations

from pydantic import Field

from sculptor.foundation.pydantic_serialization import SerializableModel

# Directory name under an agent's artifact dir holding the unified diff artifact.
DIFF_ARTIFACT_DIRNAME = "DIFF"


class DiffArtifact(SerializableModel):
    """Unified diff artifact containing all diff types."""

    object_type: str = "DiffArtifact"
    uncommitted_diff: str = ""
    target_branch_diff: str = ""  # Diff from merge-base(target, HEAD) to HEAD
    # Commit SHA of merge-base(target, HEAD) — the ref the target_branch_diff's
    # old-side line numbers reference. The frontend fetches the "old" file
    # content for hunk expansion at this commit so the line arrays stay in sync
    # with the diff (the target-branch tip may have diverged since the
    # merge-base). Empty when there is no target branch or no merge-base.
    target_branch_merge_base: str = ""
    file_errors: dict[str, str] = Field(
        default_factory=dict,
        description="Per-file diff generation errors. Maps relative file path to error message.",
    )

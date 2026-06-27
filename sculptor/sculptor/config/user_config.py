from enum import StrEnum
from typing import Annotated
from typing import Any
from typing import Literal

from loguru import logger
from pydantic import Field
from pydantic import Tag
from pydantic import model_validator
from pydantic.alias_generators import to_camel

from sculptor.config.custom_actions import CustomActionsConfig
from sculptor.foundation.pydantic_serialization import SerializableModel
from sculptor.foundation.pydantic_serialization import build_discriminator

# The free-disk warning threshold is this multiple of the hard minimum, so warnings
# fire before tasks are blocked outright.
_FREE_DISK_GB_WARN_LIMIT_MULTIPLIER: float = 3.0


class PanelLayoutConfig(SerializableModel):
    """Panel layout preferences for the workspace page."""

    zone_assignments: dict[str, str] = Field(default_factory=dict)
    active_panel_per_zone: dict[str, str] = Field(default_factory=dict)
    zone_visibility: dict[str, bool] = Field(default_factory=dict)
    zone_sizes: dict[str, float] = Field(default_factory=dict)
    zone_order: dict[str, list[str]] = Field(default_factory=dict)


class BabysitterAgentMRU(SerializableModel):
    """Inherit the workspace's most-recently-used agent type (the default)."""

    object_type: str = "mru"


class BabysitterAgentRegistered(SerializableModel):
    """Always drive a specific registered terminal agent, by registration id."""

    object_type: str = "registered"
    registration_id: str


# Discriminated union of which agent the CI Babysitter should use. Tagged by
# ``object_type`` (mirrors AgentConfigTypes in interfaces/agents/agent.py) so the
# harness kind and any registration_id are explicit and validated, and so
# serialized configs keep round-tripping by their stable discriminator.
BabysitterAgentChoice = Annotated[
    Annotated[BabysitterAgentMRU, Tag("mru")] | Annotated[BabysitterAgentRegistered, Tag("registered")],
    build_discriminator(),
]


class CIBabysitterConfig(SerializableModel):
    """Settings for the CI Babysitter — Sculptor watches open MRs and prompts an
    agent to fix pipeline failures and merge conflicts. Experimental; off by default.
    """

    enabled: bool = Field(
        default=False,
        description="Whether the CI Babysitter watches MRs and prompts an agent to fix pipeline failures and merge conflicts. Experimental; off by default.",
    )
    retry_cap: int = Field(
        default=3,
        description="After this many babysitter prompts for an MR without a passing pipeline, no further prompts are sent until the pipeline next passes.",
    )
    pipeline_failed_prompt: str = Field(
        default="Investigate the failing pipeline for this MR, identify the root cause, fix the code, commit, and push.",
        description="Prompt sent to the CI Babysitter agent when an MR's pipeline transitions to failed.",
    )
    merge_conflict_prompt: str = Field(
        default="This MR has a merge conflict with its base branch. Fetch the latest, then rebase against the base branch, resolve all conflicts, and force-push the result.",
        description="Prompt sent to the CI Babysitter agent when an MR develops a merge conflict with its base branch.",
    )
    agent: BabysitterAgentChoice = Field(
        default_factory=BabysitterAgentMRU,
        description="Which agent the CI Babysitter uses: most-recently-used (the default — inherits the workspace's most recent driveable agent type), or a pinned, specific registered terminal agent.",
    )


class UserConfig(SerializableModel):
    """Most configuration for user and for Sculptor app behavior should go here.

    All required fields must be provided or validation will fail.

    When you add a new field, you should add it as a field with a default value so that it is backwards compatible.
    """

    # App configuration:
    keybindings: dict[str, str | None] = Field(
        default_factory=dict, description="User-customized keybinding overrides"
    )
    min_free_disk_gb: float = Field(
        default=2.0,
        description="The minimum free disk space before Sculptor will stop allowing new tasks and messages",
    )
    panel_layout: PanelLayoutConfig | None = Field(
        default=None,
        description="Panel layout preferences for the workspace page",
    )
    custom_actions: CustomActionsConfig | None = Field(
        default=None,
        description="Custom action buttons configuration",
    )
    pr_creation_prompt: str = Field(
        default="Push my changes to origin and create a pull request. Check whether the repo uses GitHub (gh) or GitLab (glab) and use the appropriate tool. Write a clear description summarizing the changes.",
        description="Default prompt sent to the agent when Create PR is clicked",
    )
    pr_polling_enabled: bool = Field(
        default=True,
        description="Whether to poll for PR/MR status at all. When disabled, the workspace banner shows the last cached status and stops issuing gh/glab calls.",
    )
    pr_poll_interval_seconds: int = Field(
        default=30,
        description="How often (in seconds) to poll for PR status on open workspaces",
    )
    pr_poll_closed_multiplier: int = Field(
        default=6,
        description="Closed workspaces poll every pr_poll_interval_seconds * pr_poll_closed_multiplier seconds. Crank this up to poll closed workspaces much less often.",
    )
    pr_default_target_branch: str = Field(
        default="origin/main",
        description="Default target branch for new workspaces",
    )
    file_browser_default_split_ratio: int = Field(
        default=50,
        description="Default split ratio (percentage for diff panel) when the diff panel opens",
    )
    file_browser_tab_close_behavior: str = Field(
        default="mru",
        description="Which tab becomes active after closing: 'mru' (most recently used) or 'adjacent'",
    )
    file_browser_line_wrapping: str = Field(
        default="wrap",
        description="Diff line wrapping: 'wrap' (soft wrap) or 'scroll' (horizontal scrollbar)",
    )
    file_browser_diff_view_type: str = Field(
        default="unified",
        description="Default diff view: 'unified' or 'split'",
    )
    commit_prompt: str = Field(
        default="Stage every changed and untracked file, then commit with a comprehensive commit message. Do not leave any files unstaged.",
        description="Default prompt sent to the agent when Commit Changes is clicked",
    )
    ci_babysitter: CIBabysitterConfig = Field(
        default_factory=CIBabysitterConfig,
        description="Configuration for the CI Babysitter — watches MRs and prompts an agent to fix pipeline failures and merge conflicts.",
    )
    env_var_override_enabled: bool = Field(
        default=False,
        description="When True, .sculptor/.env values override pre-existing environment variables",
    )
    default_workspace_branch_naming_pattern: str = Field(
        default="<user>/<slug>",
        description="User-global default pattern for auto-generated workspace branch names. Supports <user> and <slug> placeholders. Overridden per-project by Project.naming_pattern.",
    )
    workspace_branch_deletion_policy: Literal["never", "delete_if_safe", "always"] = Field(
        default="delete_if_safe",
        description="What to do with a worktree workspace's auto-generated branch when the workspace is deleted: never (preserve), delete_if_safe (refuses to delete unmerged), always (force-delete).",
    )
    last_used_agent_type: str | None = Field(
        default=None,
        description=(
            "Most recently used agent type (harness) for new agents, stored as a"
            + " StoredAgentType string: 'terminal' or 'registered:<registration_id>'."
            + " Shared by the app's '+' button and the sculpt CLI so both create the"
            + " same harness by default. If None, new agents default to the bundled"
            + " 'claude-code' registered terminal agent."
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def _sanitize_custom_actions(cls, data: Any) -> Any:
        """Discard custom_actions if it doesn't match the expected schema.

        An earlier prototype stored custom_actions in a different format. Rather
        than crashing the entire config load, we silently drop the invalid value
        so the rest of the configuration is preserved.
        """
        if not isinstance(data, dict):
            return data
        # Check both snake_case (TOML/backend) and camelCase (frontend API) keys
        for key in ("custom_actions", "customActions"):
            value = data.get(key)
            if value is not None and not isinstance(value, (dict, CustomActionsConfig)):
                logger.warning("Ignoring invalid custom_actions config (expected dict, got {})", type(value).__name__)
                data[key] = None
        return data

    @property
    def free_disk_gb_warn_limit(self) -> float:
        return self.min_free_disk_gb * _FREE_DISK_GB_WARN_LIMIT_MULTIPLIER


def _generate_user_config_field_enum() -> type[StrEnum]:
    """Generate UserConfigField enum from UserConfig model fields"""
    fields = {}
    for field_name in UserConfig.model_fields.keys():
        # Convert field name to SCREAMING_SNAKE_CASE for enum constant
        enum_name = field_name.upper()
        fields[enum_name] = to_camel(field_name)
    # type checkers think this returns a StrEnum instance because they don't model functional enum creation
    # pyrefly: ignore [bad-return]
    return StrEnum("UserConfigField", fields)


UserConfigField: type[StrEnum] = _generate_user_config_field_enum()

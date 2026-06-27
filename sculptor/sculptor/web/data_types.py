import datetime
from enum import Enum
from enum import StrEnum
from pathlib import Path
from typing import Any
from typing import Literal

from pydantic import Field

from sculptor.config.settings import SculptorSettings
from sculptor.database.workspace_enums import WorkspaceInitializationStrategy
from sculptor.foundation.pydantic_serialization import SerializableModel
from sculptor.interfaces.agents.artifacts import DiffArtifact
from sculptor.primitives.ids import ProjectID
from sculptor.primitives.ids import WorkspaceID
from sculptor.services.data_model_service.api import CompletedTransaction
from sculptor.services.task_service.api import TaskMessageContainer
from sculptor.services.terminal_agent_registry.registry import TerminalAgentRegistration
from sculptor.services.workspace_service.api import GitOperationResult


class AgentTypeName(StrEnum):
    """The per-agent type chosen at creation time.

    `REGISTERED` requires a `registration_id` alongside it.
    """

    TERMINAL = "terminal"
    REGISTERED = "registered"


class WorkspaceBranchInfo(SerializableModel):
    """Current branch for a workspace's working directory."""

    current_branch: str
    workspace_id: WorkspaceID


class WorkspaceTargetBranchesInfo(SerializableModel):
    """Branches a workspace can target as its merge/diff base.

    These are the repo's remote-tracking branches, or its local branches when
    the repo has no remote, so the selector can still offer merge targets on a
    repo with no remote.
    """

    workspace_id: WorkspaceID
    target_branches: tuple[str, ...]


class PrApproval(SerializableModel):
    """A reviewer's approval status on a pull/merge request."""

    name: str
    approved: bool


class PrComment(SerializableModel):
    """An unresolved comment on a pull/merge request."""

    author: str
    file_path: str
    line: int | None
    body: str


class PrStatusInfo(SerializableModel):
    """PR status information for a workspace, streamed from backend to frontend."""

    workspace_id: WorkspaceID
    pr_state: Literal["none", "open", "merged", "closed"]
    has_conflicts: bool | None = None
    pr_iid: int | None = None
    pr_title: str | None = None
    pr_web_url: str | None = None
    pipeline_status: Literal["running", "passed", "failed"] | None = None
    pipeline_id: int | None = None
    pipeline_web_url: str | None = None
    pipeline_updated_at: str | None = None
    approvals: list[PrApproval] = Field(default_factory=list)
    unresolved_comments: list[PrComment] = Field(default_factory=list)
    error_category: (
        Literal["cli_missing", "not_authenticated", "no_access", "network_error", "rate_limited", "transient"] | None
    ) = None
    error_provider: Literal["gitlab", "github"] | None = None
    error_message: str | None = None
    mismatched_pr_iid: int | None = None
    mismatched_pr_target_branch: str | None = None
    mismatched_pr_web_url: str | None = None


class PrStatusInfoCleared(SerializableModel):
    """Sentinel pushed to the stream to clear a workspace's PR status on the frontend.

    When the workspace branch changes, the old PR status is stale. This signal
    causes the frontend atom to be set to null, showing "Checking MR/PR..." until
    the next poll result arrives.
    """

    workspace_id: WorkspaceID


class RequestModel(SerializableModel):
    pass


class CreateWorkspaceRequestV2(RequestModel):
    """Create workspace request with project_id in body (not URL)."""

    project_id: str
    initialization_strategy: WorkspaceInitializationStrategy
    source_branch: str | None = None
    description: str | None = None
    # Final branch name after user edits; required for WORKTREE workspaces.
    requested_branch_name: str | None = None
    # Diff/merge target branch. When None, the backend resolves a sensible default
    # from the repo (origin's default branch, else local main/master).
    target_branch: str | None = None


class UpdateWorkspaceRequest(RequestModel):
    description: str | None = None
    target_branch: str | None = None
    is_open: bool | None = None


class BatchUpdateOpenStateRequest(RequestModel):
    workspace_ids: list[str]
    is_open: bool


class CreateAgentRequest(RequestModel):
    """Create agent request for the '+' button flow (terminal agents take no prompt)."""

    name: str | None = None
    # None means "use the user's most-recently-used harness" (the server
    # resolves it, matching the app's "+" button default).
    agent_type: AgentTypeName | None = None
    # Required iff agent_type is REGISTERED.
    registration_id: str | None = None


class RenameAgentRequest(RequestModel):
    title: str


class ListTerminalAgentRegistrationsResponse(SerializableModel):
    """Current terminal-agent registrations (re-read from disk per request)."""

    registrations: list[TerminalAgentRegistration]


class SignalEventRequest(RequestModel):
    """A terminal-agent signal.

    `event` is a plain string so unknown events validate and reach the
    handler (forward compatibility — a closed enum would 422 on additive
    evolution). `session_id` accompanies the `session-id` event only.
    """

    event: str
    session_id: str | None = None


class TerminalInputRequest(RequestModel):
    """An automated prompt for a registered terminal agent.

    Smallest viable surface for v1: text plus whether to submit it — no
    arbitrary key injection.
    """

    text: str
    submit: bool = True


class WorkspaceResponse(SerializableModel):
    object_id: WorkspaceID
    project_id: ProjectID
    description: str
    initialization_strategy: WorkspaceInitializationStrategy
    source_branch: str | None
    target_branch: str | None
    requested_branch_name: str | None
    environment_id: str | None
    # Only meaningful on the streaming path — REST endpoints filter out deleted
    # workspaces via get_workspace(), so they never return is_deleted=True.
    is_deleted: bool
    is_open: bool
    created_at: datetime.datetime
    workspace_setup_command: str | None = None
    setup: "WorkspaceSetupSnapshot | None" = None


class PreviewBranchNameResponse(SerializableModel):
    """Resolved branch-name preview for the Add Workspace form."""

    branch_name: str


class BranchExistsResponse(SerializableModel):
    """Whether a branch already exists in a project's local repo."""

    exists: bool


class ProjectEnvVarNames(SerializableModel):
    """Environment variable names loaded from a single project's .sculptor/.env."""

    project_name: str
    project_path: str
    var_names: tuple[str, ...]


class EnvVarNamesResponse(SerializableModel):
    """Environment variable names from the global and per-project .env files."""

    global_var_names: tuple[str, ...]
    global_env_path: str
    projects: tuple[ProjectEnvVarNames, ...]


class RecentWorkspaceResponse(SerializableModel):
    """Workspace with denormalized project info and computed fields for cross-project listing."""

    object_id: WorkspaceID
    project_id: ProjectID
    description: str
    initialization_strategy: WorkspaceInitializationStrategy
    source_branch: str | None
    is_deleted: bool
    created_at: datetime.datetime
    project_name: str
    agent_count: int
    is_open: bool
    last_activity_at: datetime.datetime


class ListWorkspacesResponse(SerializableModel):
    """Response for cross-project workspace listing."""

    workspaces: list[RecentWorkspaceResponse]


class WorkspaceSetupCommandRequest(RequestModel):
    # None resets to the current default; "" means the user explicitly wants no command.
    workspace_setup_command: str | None


class NamingPatternRequest(RequestModel):
    naming_pattern: str


class ReadFileRequest(RequestModel):
    file_path: str


class OpenFileUiRequest(RequestModel):
    file_path: str
    mode: Literal["auto", "diff", "file"]


class DiscardFileRequest(RequestModel):
    """Request to discard changes for a single file in a workspace."""

    file_path: str


class WorkspaceDiffResponse(SerializableModel):
    """Response containing workspace diff artifact."""

    diff: DiffArtifact | None


class WorkspaceGitOperationResponse(SerializableModel):
    """Response from a workspace git operation."""

    result: GitOperationResult


class CommitFileInfo(SerializableModel):
    """Per-file change info within a single commit."""

    path: str
    status: Literal["M", "A", "D", "R"]
    old_path: str | None = None
    additions: int
    deletions: int


class CommitInfo(SerializableModel):
    """A single commit in the workspace history."""

    hash: str
    short_hash: str
    message: str
    author_name: str
    timestamp: str
    parent_hashes: list[str]
    files: list[CommitFileInfo]


class CommitHistoryResponse(SerializableModel):
    """Response containing commit history for a workspace branch."""

    commits: list[CommitInfo]
    fork_point: str | None


class CommitDiffResponse(SerializableModel):
    """Response containing the unified diff for a single commit."""

    diff: str
    commit_hash: str
    parent_hash: str | None


class WorkspaceFileEntry(SerializableModel):
    """A single file or directory in a workspace's file tree."""

    path: str
    type: Literal["file", "directory"]


class WorkspaceFileListResponse(SerializableModel):
    """Flat list of files and directories in a workspace."""

    files: list[WorkspaceFileEntry]


class OpenInOsRequest(RequestModel):
    """Request to open a file or its containing folder in the OS default application."""

    path: str
    action: Literal["open_file", "open_containing_folder"]


class ReadFileAtRefRequest(RequestModel):
    """Request to read a file's content at a specific git ref."""

    path: str
    git_ref: str


class ReadFileAtRefResponse(SerializableModel):
    """File content at a specific git ref, with encoding metadata."""

    content: str
    encoding: Literal["utf-8", "base64"]


class RepoInfo(SerializableModel):
    """Repository information"""

    repo_path: Path
    current_branch: str
    recent_branches: list[str]
    project_id: ProjectID
    is_gitlab_origin: bool = False
    is_github_origin: bool = False
    remote_branches: list[str] = Field(default_factory=list)


class CurrentBranchInfo(SerializableModel):
    """Lightweight repository information with just current branch"""

    current_branch: str


class SkillInfo(SerializableModel):
    """Information about a single Claude Code skill."""

    name: str
    description: str
    source: Literal["custom", "plugin"]
    file_path: str | None = None


class InitializeGitRepoRequest(RequestModel):
    """Request to initialize a directory as a git repository"""

    project_path: str


class CreateInitialCommitRequest(RequestModel):
    """Request to create an initial commit in a new git repository"""

    project_path: str


class ProjectInitializationRequest(RequestModel):
    """Request to initialize a new project"""

    project_path: str


class ConfigStatusResponse(SerializableModel):
    """Response for config status check"""

    has_project: bool
    has_dependencies_passing: bool


class ToolAvailability(SerializableModel):
    """Whether the external CLI tools onboarding checks for are on PATH."""

    claude: bool
    git: bool


class UploadFileResponse(SerializableModel):
    file_id: str


class HealthCheckResponse(SerializableModel):
    version: str
    git_sha: str
    python_version: str
    platform: str
    platform_version: str
    free_disk_gb: float
    min_free_disk_gb: float
    free_disk_gb_warn_limit: float

    uptime_seconds: float
    active_task_count: int
    data_directory: str
    install_mode: str
    install_path: str
    ci_job_id: str | None = None
    ci_ref: str | None = None


class UpdateUserConfigRequest(RequestModel):
    """Partial update for ``UserConfig``.

    ``user_config`` is a dict of only the fields the caller wants to change —
    fields absent from the dict are left at their current server-side value.
    The handler merges into the current config and re-validates as a full
    ``UserConfig``. This avoids the lost-update race where a stale
    full-object PUT clobbers fields recently changed by another writer
    (e.g. a debounced panel-layout sync overwriting a setting toggle).
    """

    user_config: dict[str, Any]


class ExternalApp(str, Enum):
    """Supported external applications for opening paths."""

    VSCODE = "vscode"
    PYCHARM = "pycharm"
    CURSOR = "cursor"
    GHOSTTY = "ghostty"
    ITERM = "iterm"
    TERMINAL = "terminal"
    FINDER = "finder"


class OpenPathInAppRequest(RequestModel):
    """Request to open a file system path in an external application."""

    path: str
    app: ExternalApp


class OpenPathInAppResult(SerializableModel):
    """Result of attempting to open a path in an external application."""

    success: bool
    error_message: str | None = None


class AgentDiagnosticsResponse(SerializableModel):
    """Diagnostics information for a specific agent."""

    session_id: str | None = None
    transcript_file_path: str | None = None
    sculptor_transcript_file_path: str | None = None


class WorkspaceSetupStatus(SerializableModel):
    """Status snapshot for a workspace setup run."""

    workspace_id: WorkspaceID
    status: Literal["not_configured", "pending", "running", "succeeded", "failed", "legacy"]
    run_id: str | None = None
    exit_code: int | None = None
    started_at: float | None = None
    finished_at: float | None = None
    log_truncated: bool = False


class WorkspaceSetupOutputChunk(SerializableModel):
    """Live output chunk for a workspace setup run.

    `data` carries raw output bytes; Pydantic encodes them as base64 over the
    wire and the frontend decodes back to bytes for display.
    """

    workspace_id: WorkspaceID
    run_id: str
    seq: int
    data: bytes


class WorkspaceSetupSnapshot(SerializableModel):
    """Per-workspace setup snapshot embedded in WorkspaceResponse."""

    status: Literal["not_configured", "pending", "running", "succeeded", "failed", "legacy"]
    run_id: str | None = None
    exit_code: int | None = None
    started_at: float | None = None
    finished_at: float | None = None
    log_truncated: bool = False


class OpenFileUiAction(SerializableModel):
    workspace_id: WorkspaceID
    file_path: str
    mode: Literal["auto", "diff", "file"]


# Generic system dependency models for unified frontend rendering


class DirectoryEntry(SerializableModel):
    """A single directory entry returned by the filesystem list endpoint."""

    name: str
    path: str


TaskUpdateTypes = CompletedTransaction
UserUpdateSourceTypes = CompletedTransaction | SculptorSettings
StreamingUpdateSourceTypes = (
    TaskMessageContainer
    | TaskUpdateTypes
    | UserUpdateSourceTypes
    | WorkspaceBranchInfo
    | WorkspaceTargetBranchesInfo
    | WorkspaceSetupStatus
    | WorkspaceSetupOutputChunk
    | PrStatusInfo
    | PrStatusInfoCleared
    | OpenFileUiAction
)

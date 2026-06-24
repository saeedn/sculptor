"""Workspace-related enums."""

from enum import auto

from sculptor.foundation.upper_case_str_enum import UpperCaseStrEnum


class WorkspaceInitializationStrategy(UpperCaseStrEnum):
    """Strategy for workspace initialization.

    WORKTREE: Work in a git worktree off the user's repository (shared `.git`).
    """

    WORKTREE = auto()


class DiffStatus(UpperCaseStrEnum):
    """Status of workspace diff generation."""

    NONE = auto()
    GENERATING = auto()
    READY = auto()

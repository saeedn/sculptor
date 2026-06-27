"""Workspace-related enums."""

from enum import auto

from sculptor.foundation.upper_case_str_enum import UpperCaseStrEnum


class DiffStatus(UpperCaseStrEnum):
    """Status of workspace diff generation."""

    NONE = auto()
    GENERATING = auto()
    READY = auto()

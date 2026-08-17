"""Reviewer finding model, shared by the review gate and the scheduler.

A leaf module (stdlib + pydantic only) so both ``review`` and
``scheduler`` can type findings without importing each other.
"""

from typing import Literal

from pydantic import BaseModel


class Finding(BaseModel):
    task_id: str | None = None
    severity: Literal["blocker", "warning"]
    summary: str
    detail: str = ""

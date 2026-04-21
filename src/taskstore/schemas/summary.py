import uuid
from datetime import date, datetime

from pydantic import BaseModel


class OverdueItem(BaseModel):
    id: uuid.UUID
    title: str
    due_date: date
    days_overdue: int


class DueSoonItem(BaseModel):
    id: uuid.UUID
    title: str
    due_date: date
    days_until: int


class StalledProject(BaseModel):
    id: uuid.UUID
    name: str
    backlog_count: int
    days_since_activity: int


class RecentlyCompleted(BaseModel):
    id: uuid.UUID
    title: str
    completed_at: datetime


class WaitingForItem(BaseModel):
    id: uuid.UUID
    title: str
    assignee: str | None
    created_by: str


class SummaryData(BaseModel):
    triage_count: int = 0
    overdue: list[OverdueItem] = []
    due_soon: list[DueSoonItem] = []
    stalled_projects: list[StalledProject] = []
    by_state_type: dict[str, int] = {}
    by_assignee: dict[str, dict[str, int]] = {}
    recently_completed: list[RecentlyCompleted] = []
    waiting_for: list[WaitingForItem] = []

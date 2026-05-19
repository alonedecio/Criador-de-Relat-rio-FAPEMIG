from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ClickUpCommentSummary(BaseModel):
    comment_id: Optional[str] = None
    date: Optional[str] = None
    user: Optional[str] = None
    email: Optional[str] = None
    comment_text: Optional[str] = None


class ClickUpChecklistItemSummary(BaseModel):
    name: str = ""
    concluido: bool = False
    marcador: str = ""


class ClickUpChecklistSummary(BaseModel):
    checklist_name: str = ""
    itens: list[ClickUpChecklistItemSummary] = Field(default_factory=list)
    total: int = 0
    concluidos: int = 0


class ClickUpTaskBase(BaseModel):
    id: str
    name: str = ""
    parent: Optional[str] = None
    toplevelparent: Optional[str] = None
    status: Optional[str] = None
    status_raw: Any = None
    priority: Optional[str] = None
    startdate: Optional[str] = None
    duedate: Optional[str] = None
    datedone: Optional[str] = None
    dateclosed: Optional[str] = None
    datecreated: Optional[str] = None
    dateupdated: Optional[str] = None
    archived: bool = False
    list_info: dict[str, Any] = Field(default_factory=dict, alias="list")
    folder: dict[str, Any] = Field(default_factory=dict)
    space: dict[str, Any] = Field(default_factory=dict)
    url: Optional[str] = None
    customfields: list[dict[str, Any]] = Field(default_factory=list)
    textcontent: str = ""
    description: str = ""
    assignees: list[dict[str, Any]] = Field(default_factory=list)


class ClickUpTaskEnriched(BaseModel):
    task_id: str
    base: ClickUpTaskBase
    description: str = ""
    textcontent: str = ""
    assignees: list[dict[str, Any]] = Field(default_factory=list)
    watchers: list[dict[str, Any]] = Field(default_factory=list)
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    tags: list[dict[str, Any]] = Field(default_factory=list)
    customfields: list[dict[str, Any]] = Field(default_factory=list)
    dependencies: list[dict[str, Any]] = Field(default_factory=list)
    linkedtasks: list[dict[str, Any]] = Field(default_factory=list)
    checklists: list[dict[str, Any]] = Field(default_factory=list)
    checklists_summary: list[ClickUpChecklistSummary] = Field(default_factory=list)
    comments: list[ClickUpCommentSummary] = Field(default_factory=list)
    comments_count: int = 0
    raw_detail_keys: list[str] = Field(default_factory=list)
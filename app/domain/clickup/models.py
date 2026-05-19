from __future__ import annotations
from typing import Any, Optional
from pydantic import BaseModel, Field


class ClickUpTaskBase(BaseModel):
    """Campos normalizados vindos da listagem base do ClickUp."""
    id:             str
    name:           str
    parent:         Optional[str] = None
    toplevelparent: Optional[str] = None
    status:         str = "pendente"
    priority:       Optional[str] = None
    startdate:      Optional[int] = None   # ← data_planejada_inicio (ms)
    duedate:        Optional[int] = None   # ← data_planejada_fim    (ms)
    datedone:       Optional[int] = None   # ← data_realizada_fim    (ms)
    dateclosed:     Optional[int] = None
    datecreated:    Optional[int] = None
    dateupdated:    Optional[int] = None
    archived:       bool = False
    url:            Optional[str] = None
    customfields:   list[dict[str, Any]] = Field(default_factory=list)
    textcontent:    str = ""
    description:    str = ""
    assignees:      list[dict[str, Any]] = Field(default_factory=list)
    folder:         Optional[dict[str, Any]] = None
    space:          Optional[dict[str, Any]] = None
    list_info:      Optional[dict[str, Any]] = None
    status_raw:     Optional[dict[str, Any]] = None


class ClickUpTaskEnriched(BaseModel):
    """Task completa do enriched snapshot — base + detalhes enriquecidos."""
    task_id:            str
    base:               ClickUpTaskBase
    description:        str = ""
    textcontent:        str = ""
    assignees:          list[dict[str, Any]] = Field(default_factory=list)
    watchers:           list[dict[str, Any]] = Field(default_factory=list)
    attachments:        list[dict[str, Any]] = Field(default_factory=list)
    tags:               list[dict[str, Any]] = Field(default_factory=list)
    customfields:       list[dict[str, Any]] = Field(default_factory=list)
    dependencies:       list[dict[str, Any]] = Field(default_factory=list)
    linkedtasks:        list[dict[str, Any]] = Field(default_factory=list)
    checklists:         list[dict[str, Any]] = Field(default_factory=list)
    checklists_summary: list[dict[str, Any]] = Field(default_factory=list)
    comments:           list[dict[str, Any]] = Field(default_factory=list)
    comments_count:     int = 0
    raw_detail_keys:    list[str] = Field(default_factory=list)

    @property
    def data_planejada_inicio_ms(self) -> Optional[int]:
        """start_date planejado em ms. Fonte: base.startdate."""
        return self.base.startdate

    @property
    def data_planejada_fim_ms(self) -> Optional[int]:
        """due_date planejado em ms. Fonte: base.duedate."""
        return self.base.duedate

    @property
    def data_realizada_fim_ms(self) -> Optional[int]:
        """Data efetiva de conclusão em ms. Fonte: base.datedone ou base.dateclosed."""
        return self.base.datedone or self.base.dateclosed


class ClickUpEnrichedSnapshot(BaseModel):
    """Envelope completo do arquivo clickup_enriched_snapshot.json."""
    metadata: dict[str, Any] = Field(default_factory=dict)
    tasks:    list[ClickUpTaskEnriched] = Field(default_factory=list)

    def index_by_id(self) -> dict[str, ClickUpTaskEnriched]:
        """Retorna dicionário task_id → task para acesso O(1)."""
        return {t.task_id: t for t in self.tasks}
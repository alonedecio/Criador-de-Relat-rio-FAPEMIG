from __future__ import annotations

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class DatasAtividade(BaseModel):
    datainicio: Optional[int] = None
    datafim: Optional[int] = None
    datafimrealizado: Optional[int] = None


class ProgressoCalculado(BaseModel):
    atrasada: bool = False
    situacaoprazo: Optional[str] = None
    duracaoprevistadias: Optional[int] = None
    duracaoefetivadias: Optional[int] = None
    mesanoinicioprevisto: Optional[str] = None
    mesanofimprevisto: Optional[str] = None
    mesanoinicioreal: Optional[str] = None
    mesanofimreal: Optional[str] = None
    previstopercentual: Optional[float] = None
    realizadopercentual: Optional[float] = None


class AtividadeTexto(BaseModel):
    desenvolvimento: Optional[str] = None
    resultados: Optional[str] = None
    justificativa: Optional[str] = None


class AtividadeReport(BaseModel):
    atividadeid: str
    numeroatividade: str
    numeroatividadeoriginal: Optional[str] = None
    titulo: str
    indicadorfisico: Optional[str] = None
    statusclickup: Optional[str] = None
    percentualrealizado: Optional[float] = None
    datas: DatasAtividade = Field(default_factory=DatasAtividade)
    desenvolvimento: Optional[str] = None
    resultados: Optional[str] = None
    justificativa: Optional[str] = None
    progressocalculado: ProgressoCalculado = Field(default_factory=ProgressoCalculado)

    def textos(self) -> AtividadeTexto:
        return AtividadeTexto(
            desenvolvimento=self.desenvolvimento,
            resultados=self.resultados,
            justificativa=self.justificativa,
        )


class ProgressoMeta(BaseModel):
    previstopercentualmedio: Optional[float] = None
    realizadopercentualmedio: Optional[float] = None


class MetaReport(BaseModel):
    item: int
    metaidoriginal: str
    meta: str
    percentualmeta: Optional[float] = None
    atividades: List[AtividadeReport] = Field(default_factory=list)
    progressocalculadometa: ProgressoMeta = Field(default_factory=ProgressoMeta)


class ReportMetadata(BaseModel):
    project_id: Optional[str] = None
    project_name: Optional[str] = None
    generated_at: Optional[str] = None
    competence: Optional[str] = None
    extra: Dict[str, Any] = Field(default_factory=dict)


class RelatorioProjeto(BaseModel):
    metadata: Dict[str, Any] = Field(default_factory=dict)
    secoesfixas: Dict[str, Any] = Field(default_factory=dict)
    itensmetaatividade: List[MetaReport] = Field(default_factory=list)

    @property
    def total_metas(self) -> int:
        return len(self.itensmetaatividade)

    @property
    def total_atividades(self) -> int:
        return sum(len(meta.atividades) for meta in self.itensmetaatividade)
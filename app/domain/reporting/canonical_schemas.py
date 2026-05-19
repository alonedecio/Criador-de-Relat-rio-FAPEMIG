from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class DatasCanonicas(BaseModel):
    data_inicio: Optional[str] = None
    data_fim: Optional[str] = None
    data_fim_realizado: Optional[str] = None


class ProgressoAtividadeCanonico(BaseModel):
    atrasada: Optional[bool] = None
    situacao_prazo: Optional[str] = None
    duracao_prevista_dias: Optional[int] = None
    duracao_efetiva_dias: Optional[int] = None
    mes_ano_inicio_previsto: Optional[str] = None
    mes_ano_fim_previsto: Optional[str] = None
    mes_ano_inicio_real: Optional[str] = None
    mes_ano_fim_real: Optional[str] = None
    previsto_percentual: Optional[float] = None
    realizado_percentual: Optional[float] = None


class TextoAtividadeCanonico(BaseModel):
    desenvolvimento: Optional[str] = ""
    resultados: Optional[str] = ""
    justificativa: Optional[str] = ""


class AtividadeCanonica(BaseModel):
    atividade_id: str
    numero_atividade: Optional[str] = None
    numero_atividade_original: Optional[str] = None
    titulo_original: Optional[str] = None
    titulo: str
    indicador_fisico: Optional[str] = None
    status_clickup: Optional[str] = None
    percentual_realizado: Optional[float] = None
    datas: DatasCanonicas
    progresso: ProgressoAtividadeCanonico
    texto: TextoAtividadeCanonico = Field(default_factory=TextoAtividadeCanonico)
    origem: Dict[str, Any] = Field(default_factory=dict)


class ProgressoMetaCanonico(BaseModel):
    previsto_percentual_medio: Optional[float] = None
    realizado_percentual_medio: Optional[float] = None


class MetaCanonica(BaseModel):
    item: str
    meta_id_original: str
    meta_nome: str
    percentual_meta: Optional[float] = None
    atividades: List[AtividadeCanonica]
    progresso: Optional[ProgressoMetaCanonico] = None


class ResumoProjetoCanonico(BaseModel):
    dados: Dict[str, Any] = Field(default_factory=dict)


class RelatorioCanonico(BaseModel):
    metadata: Dict[str, Any] = Field(default_factory=dict)
    resumo_projeto: ResumoProjetoCanonico = Field(default_factory=ResumoProjetoCanonico)
    metas: List[MetaCanonica] = Field(default_factory=list)
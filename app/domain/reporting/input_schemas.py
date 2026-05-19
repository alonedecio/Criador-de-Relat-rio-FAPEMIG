from typing import List, Optional, Dict, Any
from pydantic import BaseModel


class DatasInput(BaseModel):
    data_inicio: Optional[str] = None
    data_fim: Optional[str] = None
    data_fim_realizado: Optional[str] = None


class ProgressoCalculadoInput(BaseModel):
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


class AtividadeInput(BaseModel):
    atividade_id: str
    numero_atividade: str
    numero_atividade_original: Optional[str] = None
    titulo: str
    indicador_fisico: Optional[str] = None
    status_clickup: Optional[str] = None
    percentual_realizado: Optional[float] = None
    datas: DatasInput
    desenvolvimento: Optional[str] = None
    resultados: Optional[str] = None
    justificativa: Optional[str] = None
    progresso_calculado: ProgressoCalculadoInput


class ProgressoMetaInput(BaseModel):
    previsto_percentual_medio: Optional[float] = None
    realizado_percentual_medio: Optional[float] = None


class MetaInput(BaseModel):
    item: str
    meta_id_original: str
    meta: str
    percentual_meta: Optional[float] = None
    atividades: List[AtividadeInput]
    progresso_calculado_meta: Optional[ProgressoMetaInput] = None


class SecaoCronogramaInput(BaseModel):
    resumo_projeto: Dict[str, Any] = {}
    itens_meta_atividade: List[MetaInput]


class RelatorioInput(BaseModel):
    metadata: Dict[str, Any] = {}
    secoes_fixas: Dict[str, Any]


class RootReportInput(BaseModel):
    relatorio: RelatorioInput
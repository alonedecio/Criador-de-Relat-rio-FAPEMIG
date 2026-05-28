"""
Schemas Pydantic para o pipeline de agentes IA.

Hierarquia:
    ContextoProjeto      — estático, nível projeto  (vem de termo_outorga.py)
    ContextoAtividade    — dinâmico, por atividade   (vem de context/builders.py)
    TextosGerados        — saída do writer
    ResultadoValidacao   — saída do validator
    ResultadoAtividade   — produto final por atividade (writer + auditoria)
"""
from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class StatusValidacao(str, Enum):
    APROVADO = "aprovado"
    REPROVADO = "reprovado"
    APROVADO_COM_RESSALVA = "aprovado_com_ressalva"


class TextosGerados(BaseModel):
    """Saída estruturada do writer para uma atividade."""
    desenvolvimento: str = Field(
        description="Descrição narrativa do desenvolvimento da atividade."
    )
    resultados: str = Field(
        description="Comentário sobre resultado(s) ou ausência deles."
    )
    justificativa: str = Field(
        description=(
            "Justificativa do atraso ou adiantamento em relação à previsão. "
            "Vazio se a atividade está no prazo."
        )
    )


class ResultadoValidacao(BaseModel):
    """Saída do validator após análise dos textos gerados."""
    status: StatusValidacao
    erros: list[str] = Field(default_factory=list)
    ressalvas: list[str] = Field(default_factory=list)
    sugestoes_correcao: list[str] = Field(default_factory=list)


class AuditoriaAtividade(BaseModel):
    """Trilha auditável de uma atividade processada."""
    atividade_id: str
    tentativas: int
    status_final: StatusValidacao
    erros_encontrados: list[str] = Field(default_factory=list)
    fontes_contexto: list[str] = Field(default_factory=list)  # clickup, pdf, progresso


class ResultadoAtividade(BaseModel):
    """Produto final por atividade: textos aprovados + auditoria."""
    atividade_id: str
    meta_codigo: str
    titulo: str
    textos: TextosGerados
    auditoria: AuditoriaAtividade

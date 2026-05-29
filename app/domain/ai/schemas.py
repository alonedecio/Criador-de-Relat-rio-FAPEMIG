"""
Schemas de dados dos agentes IA.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class StatusValidacao(str, Enum):
    APROVADO   = "aprovado"
    REPROVADO  = "reprovado"
    INCOMPLETO = "incompleto"


@dataclass
class TextosGerados:
    """Saída do writer para uma atividade (3 campos)."""
    desenvolvimento: str = ""
    resultados:      str = ""
    justificativa:   str = ""


@dataclass
class AuditoriaAtividade:
    atividade_id:  str
    tentativas:    int
    status:        StatusValidacao
    feedbacks:     list[str] = field(default_factory=list)


@dataclass
class ResultadoAtividade:
    atividade_id: str
    meta_codigo:  str
    titulo:       str
    textos:       Optional[TextosGerados]
    auditoria:    AuditoriaAtividade


@dataclass
class TextosSecaoFinal:
    """Saída do writer para as seções finais do relatório (5-10)."""
    # Seção 5 — Avaliação da gestão
    capacitacoes_equipe:       str = ""
    melhorias_instalacoes:     str = ""
    dificuldades_nao_tecnicas: str = ""
    # Seção 6 — Impactos
    impactos_internos:         str = ""
    impactos_externos:         str = ""
    # Seção 7 — Produção tecnológica
    producao_tecnologica:      str = ""
    # Seção 8 — Parcerias
    parcerias_institucionais:  str = ""
    # Seção 9 — Comentário final
    comentario_final:          str = ""
    # Seção 10 — Resumo
    resumo:                    str = ""

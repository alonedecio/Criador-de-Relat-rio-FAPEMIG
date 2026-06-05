"""
Schemas de dados dos agentes IA.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class StatusValidacao(str, Enum):
    APROVADO              = "aprovado"
    APROVADO_COM_RESSALVA = "aprovado_com_ressalva"
    REPROVADO             = "reprovado"
    INCOMPLETO            = "incompleto"


@dataclass
class TextosGerados:
    """Saída do writer para uma atividade (3 campos)."""
    desenvolvimento: str = ""
    resultados:      str = ""
    justificativa:   str = ""


@dataclass
class ResultadoValidacao:
    """
    Saída do validator após avaliar os textos gerados pelo writer.
    Retornado por app.domain.ai.validator.validar_textos().
    """
    status:              StatusValidacao
    erros:               list[str] = field(default_factory=list)
    sugestoes_correcao:  list[str] = field(default_factory=list)
    observacoes:         list[str] = field(default_factory=list)


@dataclass
class AuditoriaAtividade:
    """
    Registro auditável do ciclo writer → validator → retry de uma atividade.
    status_final reflete o status da última (ou melhor) validação.
    """
    atividade_id:      str
    tentativas:        int
    status_final:      StatusValidacao
    erros_encontrados: list[str] = field(default_factory=list)
    fontes_contexto:   list[str] = field(default_factory=list)

    # Compat: alias status → status_final para leitores do JSON antigo
    @property
    def status(self) -> StatusValidacao:
        return self.status_final


@dataclass
class ResultadoAtividade:
    atividade_id: str
    meta_codigo:  str
    titulo:       str
    textos:       Optional[TextosGerados]
    auditoria:    AuditoriaAtividade


@dataclass
class TextosSecaoFinal:
    """
    Saída do writer para as seções finais do RAT FAPEMIG (tópicos 5 a 10).

    Estrutura alinhada ao modelo oficial do RAT:
      5. Avaliação da gestão do projeto
      6. Impactos internos e externos do projeto  (3 sub-campos)
      7. Produção tecnológica
      8. Parceria institucional
      9. Comentário final
      10. Resumo + palavras-chave
    """
    # ── Tópico 5 — Avaliação da gestão do projeto ─────────────────────────
    # Texto único consolidando: capacitações realizadas, melhorias físicas
    # e dificuldades não técnicas enfrentadas no período.
    avaliacao_gestao: str = ""

    # ── Tópico 6 — Impactos internos e externos ───────────────────────────
    # Sub-campo A: desdobramentos internos (mudanças organizacionais,
    # faturamento, processos internos da instituição e parceiros)
    desdobramentos_internos: str = ""
    # Sub-campo B: posicionamento de mercado (mudanças de posicionamento
    # da instituição perante mercado/sociedade proporcionadas pelo projeto)
    posicionamento_mercado: str = ""
    # Sub-campo C: benefícios sociais trazidos pelo projeto
    beneficios_sociais: str = ""

    # ── Tópico 7 — Produção tecnológica ──────────────────────────────────
    # Produtos, protótipos, patentes, processos, metodologias que surgiram
    # e não haviam sido previstos como indicadores físicos.
    producao_tecnologica: str = ""

    # ── Tópico 8 — Parceria institucional ────────────────────────────────
    # Articulações institucionais mantidas, resultados transferidos,
    # contribuição de cada parceiro.
    parcerias_institucionais: str = ""

    # ── Tópico 9 — Comentário final ──────────────────────────────────────
    # Observações relevantes que não se aplicam aos outros campos.
    comentario_final: str = ""

    # ── Tópico 10 — Resumo ───────────────────────────────────────────────
    # Resumo com até 200 palavras para divulgação externa.
    resumo: str = ""
    # Até 6 palavras-chave que caracterizam os resultados.
    palavras_chave: list[str] = field(default_factory=list)

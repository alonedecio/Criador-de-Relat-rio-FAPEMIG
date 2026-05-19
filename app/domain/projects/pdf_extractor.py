"""
Extração estruturada de metas e atividades do PDF do projeto.

Lê o ProjetoPDFIndexado e devolve:
- data de início do projeto
- por atividade: mês relativo de início, mês fim, duração
- datas absolutas calculadas a partir do início do projeto
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from dateutil.relativedelta import relativedelta
from typing import Optional

from app.domain.projects.pdf_reader import ProjetoPDFIndexado


# ── modelos de saída ──────────────────────────────────────────────────────────

@dataclass
class AtividadePDF:
    codigo:          str            # ex: "1.1", "2.3"
    meta_codigo:     str            # ex: "1", "2"
    mes_inicio_rel:  int            # relativo ao início do projeto
    mes_fim_rel:     int
    duracao_meses:   int
    data_inicio_abs: Optional[date] = None
    data_fim_abs:    Optional[date] = None


@dataclass
class ProjetoExtraido:
    data_inicio:  Optional[date]
    atividades:   list[AtividadePDF] = field(default_factory=list)

    def por_codigo(self, codigo: str) -> Optional[AtividadePDF]:
        """Busca atividade pelo código exato (ex: '1.1')."""
        for a in self.atividades:
            if a.codigo == codigo:
                return a
        return None


# ── regexes ───────────────────────────────────────────────────────────────────

# Data de início do projeto — formatos comuns em termos FAPEMIG
_RE_DATA_INICIO = re.compile(
    r"(?:in[íi]cio|vigência|data\s+de\s+in[íi]cio)[^\d]*"
    r"(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](\d{4})",
    re.IGNORECASE,
)

# Bloco de meta: "META 1" ou "Meta 1"
_RE_META = re.compile(r"\bMETA\s+(\d+)\b", re.IGNORECASE)

# Atividade com código: "1.1" ou "Atividade 1.1"
_RE_ATIVIDADE = re.compile(
    r"(?:atividade\s+)?(\d+)\.(\d+)",
    re.IGNORECASE,
)

# Mês início / mês fim / duração — formatos típicos de tabelas PDF
_RE_MES_INICIO = re.compile(
    r"m[eê]s\s+(?:de\s+)?in[íi]cio[^\d]*(\d{1,2})",
    re.IGNORECASE,
)
_RE_MES_FIM = re.compile(
    r"m[eê]s\s+(?:de\s+)?(?:fim|t[eé]rmino|final)[^\d]*(\d{1,2})",
    re.IGNORECASE,
)
_RE_DURACAO = re.compile(
    r"dura[çc][aã]o[^\d]*(\d{1,2})",
    re.IGNORECASE,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _extrair_data_inicio(texto: str) -> Optional[date]:
    m = _RE_DATA_INICIO.search(texto)
    if not m:
        return None
    try:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


def _mes_rel_para_data(data_inicio: date, mes_rel: int) -> date:
    """Converte mês relativo (1-based) em data absoluta."""
    return data_inicio + relativedelta(months=mes_rel - 1)


def _ultimo_dia_mes(d: date) -> date:
    """Retorna o último dia do mês de uma data."""
    proximo = d + relativedelta(months=1)
    return proximo.replace(day=1) - relativedelta(days=1)


# ── extração principal ────────────────────────────────────────────────────────

def _extrair_atividades(texto: str, data_inicio: Optional[date]) -> list[AtividadePDF]:
    """
    Varre o texto linha a linha mantendo contexto de meta atual.
    Para cada bloco de atividade, tenta extrair mês início, fim e duração
    nas linhas seguintes (janela de 10 linhas).
    """
    linhas = texto.splitlines()
    atividades: list[AtividadePDF] = []
    meta_atual = "0"

    for i, linha in enumerate(linhas):
        # atualiza meta corrente
        m_meta = _RE_META.search(linha)
        if m_meta:
            meta_atual = m_meta.group(1)

        # detecta atividade
        m_atv = _RE_ATIVIDADE.search(linha)
        if not m_atv:
            continue

        meta_codigo = m_atv.group(1)
        atv_num     = m_atv.group(2)
        codigo      = f"{meta_codigo}.{atv_num}"

        # janela de busca: linha atual + 10 linhas seguintes
        janela = "\n".join(linhas[i: i + 10])

        m_ini  = _RE_MES_INICIO.search(janela)
        m_fim  = _RE_MES_FIM.search(janela)
        m_dur  = _RE_DURACAO.search(janela)

        if not (m_ini and m_fim):
            continue

        mes_ini = int(m_ini.group(1))
        mes_fim = int(m_fim.group(1))
        duracao = int(m_dur.group(1)) if m_dur else (mes_fim - mes_ini + 1)

        # datas absolutas
        if data_inicio:
            dt_ini = _mes_rel_para_data(data_inicio, mes_ini)
            dt_fim = _ultimo_dia_mes(_mes_rel_para_data(data_inicio, mes_fim))
        else:
            dt_ini = dt_fim = None

        atividades.append(AtividadePDF(
            codigo=codigo,
            meta_codigo=meta_codigo,
            mes_inicio_rel=mes_ini,
            mes_fim_rel=mes_fim,
            duracao_meses=duracao,
            data_inicio_abs=dt_ini,
            data_fim_abs=dt_fim,
        ))

    return atividades


def extrair_projeto(pdf: ProjetoPDFIndexado) -> ProjetoExtraido:
    """
    Ponto de entrada principal.
    Recebe ProjetoPDFIndexado e devolve ProjetoExtraido com
    data de início e lista de AtividadePDF com datas calculadas.
    """
    texto        = pdf.texto_completo
    data_inicio  = _extrair_data_inicio(texto)
    atividades   = _extrair_atividades(texto, data_inicio)

    return ProjetoExtraido(
        data_inicio=data_inicio,
        atividades=atividades,
    )
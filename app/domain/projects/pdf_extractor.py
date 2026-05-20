"""
Extração estruturada de metas e atividades do PDF do projeto.

Lê o ProjetoPDFIndexado e devolve:
- data de início do projeto
- por atividade: mês relativo de início, mês fim, duração
- datas absolutas calculadas a partir do início do projeto

NOTA DE ROBUSTEZ:
  O texto extraído por OCR frequentemente perde acentuação (ex: "Ms de incio"
  em vez de "Mês de início"). Toda busca de padrões é feita sobre uma versão
  normalizada (sem acentos, lowercase) do texto, enquanto a estrutura original
  é preservada para outros usos.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from dateutil.relativedelta import relativedelta
from typing import Optional

from app.domain.projects.pdf_reader import ProjetoPDFIndexado


# ── modelos de saída ──────────────────────────────────────────────────────────

@dataclass
class AtividadePDF:
    codigo:          str             # ex: "1.1", "2.3"
    meta_codigo:     str             # ex: "1", "2"
    mes_inicio_rel:  int             # relativo ao início do projeto (1-based)
    mes_fim_rel:     int
    duracao_meses:   int
    data_inicio_abs: Optional[date] = None
    data_fim_abs:    Optional[date] = None


@dataclass
class ProjetoExtraido:
    data_inicio: Optional[date]
    atividades:  list[AtividadePDF] = field(default_factory=list)

    def por_codigo(self, codigo: str) -> Optional[AtividadePDF]:
        """Busca atividade pelo código exato (ex: '1.1')."""
        for a in self.atividades:
            if a.codigo == codigo:
                return a
        return None


# ── normalização ──────────────────────────────────────────────────────────────

def _normalizar(texto: str) -> str:
    """
    Remove acentos e converte para lowercase.
    Essencial para matching robusto contra texto extraído por OCR,
    que frequentemente perde diacríticos (ã, é, í, ç, etc.).

    Exemplo:
        "Mês de início"  →  "mes de inicio"
        "Ms de incio"    →  "ms de incio"   (já sem acento, só lowercase)
        "Duração"        →  "duracao"
        "Durao"          →  "durao"
    """
    return (
        unicodedata.normalize("NFD", texto)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )


# ── regexes (operam sobre texto normalizado) ──────────────────────────────────

# Data de início do projeto — suporta "Data de início", "Data de inicio",
# "Vigência", "Início" com ou sem acento (texto já normalizado).
_RE_DATA_INICIO = re.compile(
    r"(?:inicio|vigencia|data\s+de\s+inicio|data\s+inicio)[^\d]*"
    r"(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](\d{4})",
    re.IGNORECASE,
)

# Fallback: captura qualquer "DD/MM/YYYY" próximo a palavras-chave de projeto
_RE_DATA_FALLBACK = re.compile(
    r"(\d{2})[\/\-\.](\d{2})[\/\-\.](\d{4})",
)

# Bloco de meta
_RE_META = re.compile(r"\bmeta\s+(\d+)\b")

# Atividade com código: "1.1", "Atividade 1.1", "Descrição 1.1"
_RE_ATIVIDADE = re.compile(
    r"(?:atividade|descri[çc]?[aã]?o)?\s*(\d+)\.(\d+)",
)

# Mês início — aceita com e sem acento, "de" opcional:
#   "Mês de início 1", "Ms de incio 1", "Mês início: 1", "Ms inicio 1"
_RE_MES_INICIO = re.compile(
    r"m[eê]?s\s+(?:de\s+)?ini[cç][íi]?o[^\d]*(\d{1,2})",
)

# Mês fim — aceita "fim", "termino", "término", "final"
_RE_MES_FIM = re.compile(
    r"mes\s+de\s+(?:fim|termino|final|m)[^\d]*(\d{1,2})",
)

# Duração — aceita "Duração", "Duracao", "Durao" (OCR agressivo)
_RE_DURACAO = re.compile(
    r"dura[cç]?[aã]?o[^\d]*(\d{1,2})",
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _extrair_data_inicio(texto_norm: str, texto_orig: str) -> Optional[date]:
    """
    Tenta extrair a data de início do projeto.
    Busca primeiro pelo padrão com palavras-chave; se não achar,
    usa a primeira data DD/MM/YYYY encontrada no texto como fallback.
    Retorna None se nenhuma data válida for encontrada.
    """
    m = _RE_DATA_INICIO.search(texto_norm)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            pass

    # fallback: primeira data plausível no texto original
    for m in _RE_DATA_FALLBACK.finditer(texto_orig):
        try:
            d = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            # ignora datas muito antigas ou futuras demais
            if 2000 <= d.year <= 2040:
                return d
        except ValueError:
            continue

    return None


def _mes_rel_para_data(data_inicio: date, mes_rel: int) -> date:
    """Converte mês relativo (1-based) em data absoluta (primeiro dia do mês)."""
    return data_inicio + relativedelta(months=mes_rel - 1)


def _ultimo_dia_mes(d: date) -> date:
    """Retorna o último dia do mês de uma data."""
    return (d + relativedelta(months=1)).replace(day=1) - relativedelta(days=1)


def _validar_meses(mes_ini: int, mes_fim: int, duracao: int) -> bool:
    """Validade básica: valores positivos, fim >= início, duração coerente."""
    if mes_ini < 1 or mes_fim < 1 or mes_ini > mes_fim:
        return False
    if duracao < 1 or duracao > 60:
        return False
    return True


# ── extração principal ────────────────────────────────────────────────────────

def _extrair_atividades(
    texto_norm: str,
    data_inicio: Optional[date],
    janela_linhas: int = 15,
) -> list[AtividadePDF]:
    """
    Varre o texto normalizado linha a linha, mantendo contexto da meta atual.

    Para cada linha que contenha um código de atividade (ex: "1.1"),
    busca mês início, fim e duração numa janela de `janela_linhas` linhas
    seguintes. Ignora atividades sem mês início E fim encontrados.

    Deduplicação: se o mesmo código aparecer mais de uma vez, prevalece
    a primeira ocorrência com dados completos.
    """
    linhas = texto_norm.splitlines()
    atividades: list[AtividadePDF] = []
    codigos_vistos: set[str] = set()
    meta_atual = "0"

    for i, linha in enumerate(linhas):

        # atualiza meta corrente
        m_meta = _RE_META.search(linha)
        if m_meta:
            meta_atual = m_meta.group(1)

        # detecta código de atividade
        m_atv = _RE_ATIVIDADE.search(linha)
        if not m_atv:
            continue

        meta_codigo = m_atv.group(1)
        atv_num     = m_atv.group(2)
        codigo      = f"{meta_codigo}.{atv_num}"

        if codigo in codigos_vistos:
            continue

        # janela de busca
        janela = "\n".join(linhas[i : i + janela_linhas])

        m_ini = _RE_MES_INICIO.search(janela)
        m_fim = _RE_MES_FIM.search(janela)
        m_dur = _RE_DURACAO.search(janela)

        if not (m_ini and m_fim):
            continue

        mes_ini = int(m_ini.group(1))
        mes_fim = int(m_fim.group(1))
        duracao = int(m_dur.group(1)) if m_dur else (mes_fim - mes_ini + 1)

        if not _validar_meses(mes_ini, mes_fim, duracao):
            continue

        # datas absolutas
        if data_inicio:
            dt_ini = _mes_rel_para_data(data_inicio, mes_ini)
            dt_fim = _ultimo_dia_mes(_mes_rel_para_data(data_inicio, mes_fim))
        else:
            dt_ini = dt_fim = None

        codigos_vistos.add(codigo)
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
    data de início e lista de AtividadePDF com datas absolutas calculadas.

    Todo o matching interno é feito sobre texto normalizado (sem acentos),
    tornando a extração robusta a falhas de OCR.
    """
    texto_orig = pdf.texto_completo
    texto_norm = _normalizar(texto_orig)

    data_inicio = _extrair_data_inicio(texto_norm, texto_orig)
    atividades  = _extrair_atividades(texto_norm, data_inicio)

    return ProjetoExtraido(
        data_inicio=data_inicio,
        atividades=atividades,
    )
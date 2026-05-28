"""
ExtraÃ§Ã£o estruturada de metas e atividades do PDF do projeto.

LÃª o ProjetoPDFIndexado e devolve:
- data de inÃ­cio do projeto
- por atividade: mÃªs relativo de inÃ­cio, mÃªs fim, duraÃ§Ã£o
- datas absolutas calculadas a partir do inÃ­cio do projeto

NOTA DE ROBUSTEZ:
  O texto extraÃ­do por OCR frequentemente perde acentuaÃ§Ã£o (ex: "Ms de incio"
  em vez de "MÃªs de inÃ­cio"). Toda busca de padrÃµes Ã© feita sobre uma versÃ£o
  normalizada (sem acentos, lowercase) do texto, enquanto a estrutura original
  Ã© preservada para outros usos.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from dateutil.relativedelta import relativedelta
from typing import Optional

from app.domain.projects.pdf_reader import ProjetoPDFIndexado


# â”€â”€ modelos de saÃ­da â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@dataclass
class AtividadePDF:
    codigo:          str             # ex: "1.1", "2.3"
    meta_codigo:     str             # ex: "1", "2"
    mes_inicio_rel:  int             # relativo ao inÃ­cio do projeto (1-based)
    mes_fim_rel:     int
    duracao_meses:   int
    data_inicio_abs: Optional[date] = None
    data_fim_abs:    Optional[date] = None


@dataclass
class ProjetoExtraido:
    data_inicio: Optional[date]
    atividades:  list[AtividadePDF] = field(default_factory=list)

    def por_codigo(self, codigo: str) -> Optional[AtividadePDF]:
        """Busca atividade pelo cÃ³digo exato (ex: '1.1')."""
        for a in self.atividades:
            if a.codigo == codigo:
                return a
        return None


# â”€â”€ normalizaÃ§Ã£o â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _normalizar(texto: str) -> str:
    """
    Remove acentos e converte para lowercase.
    Essencial para matching robusto contra texto extraÃ­do por OCR,
    que frequentemente perde diacrÃ­ticos (Ã£, Ã©, Ã­, Ã§, etc.).

    Exemplo:
        "MÃªs de inÃ­cio"  â†’  "mes de inicio"
        "Ms de incio"    â†’  "ms de incio"   (jÃ¡ sem acento, sÃ³ lowercase)
        "DuraÃ§Ã£o"        â†’  "duracao"
        "Durao"          â†’  "durao"
    """
    return (
        unicodedata.normalize("NFD", texto)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )


# â”€â”€ regexes (operam sobre texto normalizado) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

# Data de inÃ­cio do projeto â€” suporta "Data de inÃ­cio", "Data de inicio",
# "VigÃªncia", "InÃ­cio" com ou sem acento (texto jÃ¡ normalizado).
_RE_DATA_INICIO = re.compile(
    r"(?:inicio|vigencia|data\s+de\s+inicio|data\s+inicio)[^\d]*"
    r"(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](\d{4})",
    re.IGNORECASE,
)

# Fallback: captura qualquer "DD/MM/YYYY" prÃ³ximo a palavras-chave de projeto
_RE_DATA_FALLBACK = re.compile(
    r"(\d{2})[\/\-\.](\d{2})[\/\-\.](\d{4})",
)

# Bloco de meta
_RE_META = re.compile(r"\bmeta\s+(\d+)\b")

# Atividade com cÃ³digo: "1.1", "Atividade 1.1", "DescriÃ§Ã£o 1.1"
_RE_ATIVIDADE = re.compile(
    r"(?:atividade|descri[Ã§c]?[aÃ£]?o)?\s*(\d+)\.(\d+)",
)

# MÃªs inÃ­cio â€” aceita com e sem acento, "de" opcional:
#   "MÃªs de inÃ­cio 1", "Ms de incio 1", "MÃªs inÃ­cio: 1", "Ms inicio 1"
_RE_MES_INICIO = re.compile(
    r"m[eÃª]?s\s+(?:de\s+)?ini[cÃ§][Ã­i]?o[^\d]*(\d{1,2})",
)

# MÃªs fim â€” aceita "fim", "termino", "tÃ©rmino", "final"
_RE_MES_FIM = re.compile(
    r"mes\s+de\s+(?:fim|termino|final|m)[^\d]*(\d{1,2})",
)

# DuraÃ§Ã£o â€” aceita "DuraÃ§Ã£o", "Duracao", "Durao" (OCR agressivo)
_RE_DURACAO = re.compile(
    r"dura[cÃ§]?[aÃ£]?o[^\d]*(\d{1,2})",
)


# â”€â”€ helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _extrair_data_inicio(texto_norm: str, texto_orig: str) -> Optional[date]:
    """
    Tenta extrair a data de inÃ­cio do projeto.
    Busca primeiro pelo padrÃ£o com palavras-chave; se nÃ£o achar,
    usa a primeira data DD/MM/YYYY encontrada no texto como fallback.
    Retorna None se nenhuma data vÃ¡lida for encontrada.
    """
    m = _RE_DATA_INICIO.search(texto_norm)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            pass

    # fallback: primeira data plausÃ­vel no texto original
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
    """Converte mÃªs relativo (1-based) em data absoluta (primeiro dia do mÃªs)."""
    return data_inicio + relativedelta(months=mes_rel - 1)


def _ultimo_dia_mes(d: date) -> date:
    """Retorna o Ãºltimo dia do mÃªs de uma data."""
    return (d + relativedelta(months=1)).replace(day=1) - relativedelta(days=1)


def _validar_meses(mes_ini: int, mes_fim: int, duracao: int) -> bool:
    """Validade bÃ¡sica: valores positivos, fim >= inÃ­cio, duraÃ§Ã£o coerente."""
    if mes_ini < 1 or mes_fim < 1 or mes_ini > mes_fim:
        return False
    if duracao < 1 or duracao > 60:
        return False
    return True


# â”€â”€ extraÃ§Ã£o principal â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _extrair_atividades(
    texto_norm: str,
    data_inicio: Optional[date],
    janela_linhas: int = 15,
) -> list[AtividadePDF]:
    """
    Varre o texto normalizado linha a linha, mantendo contexto da meta atual.

    Para cada linha que contenha um cÃ³digo de atividade (ex: "1.1"),
    busca mÃªs inÃ­cio, fim e duraÃ§Ã£o numa janela de `janela_linhas` linhas
    seguintes. Ignora atividades sem mÃªs inÃ­cio E fim encontrados.

    DeduplicaÃ§Ã£o: se o mesmo cÃ³digo aparecer mais de uma vez, prevalece
    a primeira ocorrÃªncia com dados completos.
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

        # detecta cÃ³digo de atividade
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
    data de inÃ­cio e lista de AtividadePDF com datas absolutas calculadas.

    Todo o matching interno Ã© feito sobre texto normalizado (sem acentos),
    tornando a extraÃ§Ã£o robusta a falhas de OCR.
    """
    texto_orig = pdf.texto_completo
    texto_norm = _normalizar(texto_orig)

    data_inicio = _extrair_data_inicio(texto_norm, texto_orig)
    atividades  = _extrair_atividades(texto_norm, data_inicio)

    return ProjetoExtraido(
        data_inicio=data_inicio,
        atividades=atividades,
    )


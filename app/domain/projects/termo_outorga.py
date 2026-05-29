"""
Extração de contexto institucional do Termo de Outorga (PDF FAPEMIG).

Responsabilidades:
- Ler o PDF do termo via ProjetoPDFIndexado (pdf_reader já existente)
- Extrair objetivo geral, objetivos específicos e metas pactuadas
- Produzir ContextoProjeto — injetado UMA VEZ na sessão dos agentes

O ContextoProjeto é contexto ESTÁTICO de nível projeto.
Diferente do ContextoAtividade, que é dinâmico por atividade.

Formato do PDF FAPEMIG (Plano de Trabalho):
  - Metas listadas na seção "Metas" como:
      Meta:
      1 - Criar e estruturar fisicamente...
      Meta:
      2 - Formalizar o CIEU...
  - Objetivos específicos embutidos no campo "03. Objetivo geral e específico(s);"
    como parágrafo único com numeração: "Objetivos específicos: 1. ... 2. ..."
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Optional

from app.domain.projects.pdf_reader import ProjetoPDFIndexado


# ── modelos ──────────────────────────────────────────────────────────────────

@dataclass
class MetaPactuada:
    numero: str          # ex: "1", "13"
    descricao: str       # texto da meta conforme consta no termo
    indicador: str = "" # indicador físico/quantitativo, se extraído


@dataclass
class ContextoProjeto:
    """
    Contexto institucional estático do projeto.
    Carregado uma vez e reutilizado em todas as atividades.
    """
    titulo_projeto: str
    financiador: str
    objetivo_geral: str
    objetivos_especificos: list[str] = field(default_factory=list)
    metas_pactuadas: list[MetaPactuada] = field(default_factory=list)
    vigencia: str = ""
    vocabulario_chave: list[str] = field(default_factory=list)

    def meta_por_numero(self, numero: str) -> Optional[MetaPactuada]:
        for m in self.metas_pactuadas:
            if m.numero == numero:
                return m
        return None

    def resumo_para_prompt(self) -> str:
        """
        Retorna bloco de texto compacto para injeção no system prompt dos agentes.
        Mantém apenas o essencial para não poluir o contexto da LLM.
        """
        metas_txt = "\n".join(
            f"  Meta {m.numero}: {m.descricao[:120]}"
            for m in self.metas_pactuadas
        )
        objs_txt = "\n".join(f"  {i+1}. {o[:150]}" for i, o in enumerate(self.objetivos_especificos))
        vocab_txt = ", ".join(self.vocabulario_chave) if self.vocabulario_chave else "N/D"

        return (
            f"PROJETO: {self.titulo_projeto}\n"
            f"FINANCIADOR: {self.financiador}\n"
            f"VIGÊNCIA: {self.vigencia}\n\n"
            f"OBJETIVO GERAL:\n  {self.objetivo_geral}\n\n"
            f"OBJETIVOS ESPECÍFICOS:\n{objs_txt}\n\n"
            f"METAS PACTUADAS:\n{metas_txt}\n\n"
            f"VOCABULÁRIO INSTITUCIONAL DO PROJETO: {vocab_txt}"
        )


# ── normalização ─────────────────────────────────────────────────────────────

def _norm(texto: str) -> str:
    return (
        unicodedata.normalize("NFD", texto)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )


# ── regexes ──────────────────────────────────────────────────────────────────

# Objetivo geral: extrai do parágrafo após "Objetivo Geral:"
_RE_OBJETIVO_GERAL = re.compile(
    r"objetivo\s+geral\s*:\s*(.+?)(?=objetivos?\s+especif|$)",
    re.IGNORECASE | re.DOTALL,
)

# Objetivos específicos: bloco após "Objetivos específicos:", antes da próxima seção
_RE_OBJ_ESPECIFICOS = re.compile(
    r"objetivos?\s+especif[^:]*:\s*(.+?)(?=\n\n|\d{2}\.|$)",
    re.IGNORECASE | re.DOTALL,
)

# Metas no formato FAPEMIG:
#   Meta:\n1 - Criar e estruturar...
#   Meta:\n2 - Formalizar...
# Captura o número e o texto em linha separada do marcador "Meta:"
_RE_META_FAPEMIG = re.compile(
    r"meta\s*:\s*\n\s*(\d+)\s*[-–]\s*([^\n]{10,})",
    re.IGNORECASE,
)

# Fallback: "Meta N - descricao" ou "Meta N: descricao" em linha única
_RE_META_INLINE = re.compile(
    r"meta\s+(\d+)\s*[-–:]\s*([^\n]{10,})",
    re.IGNORECASE,
)

_RE_VIGENCIA = re.compile(
    r"data\s+de\s+in[ií]cio[^:\n]*:\s*([\d]{2}/[\d]{2}/[\d]{4}).*?"
    r"data\s+t[eé]rmino[^:\n]*:\s*([\d]{2}/[\d]{2}/[\d]{4})",
    re.IGNORECASE | re.DOTALL,
)

_RE_FINANCIADOR = re.compile(
    r"(fapemig|sede|cnpq|finep|capes|mec|mcti)",
    re.IGNORECASE,
)

_RE_TITULO = re.compile(
    r"t[ií]tulo\s*:\s*\n?([^\n]{10,})",
    re.IGNORECASE,
)

# Vocabulário técnico típico de projetos de inovação/incubação
_VOCAB_SEED = [
    "pré-incubação", "incubação", "ecossistema de inovação",
    "empreendedorismo", "bootcamp", "design thinking",
    "modelagem de negócios", "mentoria", "prototipagem",
    "trilha de formação", "empresa júnior", "núcleo de estudo",
    "CIEU", "UFLA", "FAPEMIG", "SEDE", "IpêStart", "IpêTech",
    "INBATEC", "pitch", "hackathon", "pré-incubação",
    "ideação",
]


# ── extratores ───────────────────────────────────────────────────────────────

def _extrair_titulo(texto: str) -> str:
    m = _RE_TITULO.search(texto)
    if m:
        return m.group(1).strip()[:200]
    # fallback: primeira linha não-vazia com mais de 20 chars
    for linha in texto.splitlines():
        l = linha.strip()
        if len(l) > 20:
            return l[:200]
    return "Projeto sem título identificado"


def _extrair_financiador(texto: str) -> str:
    m = _RE_FINANCIADOR.search(texto)
    return m.group(1).upper() if m else "N/D"


def _extrair_vigencia(texto: str) -> str:
    m = _RE_VIGENCIA.search(texto)
    if m:
        return f"{m.group(1)} a {m.group(2)}"
    # fallback: busca por datas isoladas de início e fim
    datas = re.findall(r"[\d]{2}/[\d]{2}/[\d]{4}", texto)
    if len(datas) >= 2:
        return f"{datas[0]} a {datas[1]}"
    return ""


def _extrair_objetivo_geral(texto: str) -> str:
    m = _RE_OBJETIVO_GERAL.search(texto)
    if m:
        trecho = m.group(1).strip()
        # Remove o bloco de objetivos específicos se capturado junto
        trecho = re.split(r"objetivos?\s+especif", trecho, flags=re.IGNORECASE)[0]
        return " ".join(trecho.split())[:600]
    return "Objetivo geral não identificado no documento."


def _extrair_objetivos_especificos(texto: str) -> list[str]:
    m = _RE_OBJ_ESPECIFICOS.search(texto)
    if not m:
        return []
    bloco = m.group(1).strip()
    # Quebra por padrão de numeração: "1. ", "2. " etc.
    itens = re.split(r"(?=\d+\.\s)", bloco)
    result = []
    for item in itens:
        item = re.sub(r"^\d+\.\s*", "", item).strip()
        item = " ".join(item.split())
        if len(item) > 15:
            result.append(item[:300])
    return result[:10]  # máximo 10 objetivos


def _extrair_metas(texto: str) -> list[MetaPactuada]:
    """
    Extrai metas no formato FAPEMIG:
      Meta:\n1 - Criar e estruturar...
    Com fallback para formato inline:
      Meta 1 - Criar e estruturar...
    """
    vistas: set[str] = set()
    metas: list[MetaPactuada] = []

    # Tenta formato FAPEMIG primeiro ("Meta:\n1 - descricao")
    for m in _RE_META_FAPEMIG.finditer(texto):
        numero = m.group(1)
        if numero in vistas:
            continue
        vistas.add(numero)
        descricao = " ".join(m.group(2).split())[:300]
        metas.append(MetaPactuada(numero=numero, descricao=descricao))

    # Fallback: formato inline ("Meta 1 - descricao")
    if not metas:
        for m in _RE_META_INLINE.finditer(texto):
            numero = m.group(1)
            if numero in vistas:
                continue
            vistas.add(numero)
            descricao = " ".join(m.group(2).split())[:300]
            metas.append(MetaPactuada(numero=numero, descricao=descricao))

    return sorted(metas, key=lambda x: int(x.numero))


def _extrair_vocabulario(texto: str) -> list[str]:
    """Filtra quais termos do vocabulário-semente realmente aparecem no texto."""
    texto_lower = texto.lower()
    return [t for t in _VOCAB_SEED if t.lower() in texto_lower]


# ── ponto de entrada ─────────────────────────────────────────────────────────

def extrair_contexto_projeto(pdf: ProjetoPDFIndexado) -> ContextoProjeto:
    """
    Extrai o ContextoProjeto a partir do PDF do Termo de Outorga FAPEMIG.

    Args:
        pdf: ProjetoPDFIndexado já carregado pelo pdf_reader existente.

    Returns:
        ContextoProjeto pronto para ser injetado no system prompt dos agentes.
    """
    texto_orig = pdf.texto_completo

    return ContextoProjeto(
        titulo_projeto=_extrair_titulo(texto_orig),
        financiador=_extrair_financiador(texto_orig),
        vigencia=_extrair_vigencia(texto_orig),
        objetivo_geral=_extrair_objetivo_geral(texto_orig),
        objetivos_especificos=_extrair_objetivos_especificos(texto_orig),
        metas_pactuadas=_extrair_metas(texto_orig),
        vocabulario_chave=_extrair_vocabulario(texto_orig),
    )

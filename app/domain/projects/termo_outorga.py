"""
Extração de contexto institucional do Termo de Outorga (PDF).

Responsabilidades:
- Ler o PDF do termo via ProjetoPDFIndexado (pdf_reader já existente)
- Extrair objetivo geral, objetivos específicos e metas pactuadas
- Produzir ContextoProjeto — injetado UMA VEZ na sessão dos agentes

O ContextoProjeto é contexto ESTÁTICO de nível projeto.
Diferente do ContextoAtividade, que é dinâmico por atividade.
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
        objs_txt = "\n".join(f"  - {o[:120]}" for o in self.objetivos_especificos)
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

_RE_OBJETIVO_GERAL = re.compile(
    r"objetivo\s+geral[:\s]+(.+?)(?=objetivo\s+especif|meta|\n\n|$)",
    re.IGNORECASE | re.DOTALL,
)

_RE_OBJ_ESPECIFICOS = re.compile(
    r"objetivos?\s+especif[^:]*:[\s]*(.+?)(?=meta\s+\d|\n\n\n|$)",
    re.IGNORECASE | re.DOTALL,
)

_RE_META_BLOCO = re.compile(
    r"meta\s+(\d+)[^\n]*[:\-]?\s*([^\n]{10,})",
    re.IGNORECASE,
)

_RE_VIGENCIA = re.compile(
    r"vig[eê]ncia[^:]*:[^\n]*([\d]{2}/[\d]{2}/[\d]{4})[^\n]*([\d]{2}/[\d]{2}/[\d]{4})",
    re.IGNORECASE,
)

_RE_FINANCIADOR = re.compile(
    r"(fapemig|sede|cnpq|finep|capes|mec|mcti)",
    re.IGNORECASE,
)

_RE_TITULO = re.compile(
    r"(?:t[ií]tulo|projeto)[^:\n]*:[\s]*([^\n]{10,})",
    re.IGNORECASE,
)

# Vocabulário técnico típico de projetos de inovação/incubação
_VOCAB_SEED = [
    "pré-incubação", "incubação", "ecossistema de inovação",
    "empreendedorismo", "bootcamp", "design thinking",
    "modelagem de negócios", "mentoria", "prototipagem",
    "trilha de formação", "empresa júnior", "núcleo de estudo",
    "CIEU", "UFLA", "FAPEMIG", "SEDE",
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
    return ""


def _extrair_objetivo_geral(texto_norm: str, texto_orig: str) -> str:
    m = _RE_OBJETIVO_GERAL.search(texto_norm)
    if m:
        # recupera trecho equivalente no texto original para manter acentos
        inicio = m.start(1)
        fim = m.end(1)
        trecho = texto_orig[inicio:fim].strip()
        return " ".join(trecho.split())[:600]
    return "Objetivo geral não identificado no documento."


def _extrair_objetivos_especificos(texto_norm: str, texto_orig: str) -> list[str]:
    m = _RE_OBJ_ESPECIFICOS.search(texto_norm)
    if not m:
        return []
    inicio = m.start(1)
    fim = m.end(1)
    bloco = texto_orig[inicio:fim]
    # quebra por marcadores de lista ou ponto-e-vírgula
    itens = re.split(r"[;\n]|(?<=\.)\s+(?=[a-záéíóúA-ZÁÉÍÓÚ])", bloco)
    result = []
    for item in itens:
        item = item.strip().lstrip("•-–·*abcdefghijklmnopqrstuvwxyz) ").strip()
        if len(item) > 15:
            result.append(item[:300])
    return result[:10]  # máximo 10 objetivos


def _extrair_metas(texto_norm: str, texto_orig: str) -> list[MetaPactuada]:
    metas = []
    vistas: set[str] = set()
    for m in _RE_META_BLOCO.finditer(texto_norm):
        numero = m.group(1)
        if numero in vistas:
            continue
        vistas.add(numero)
        # recupera descrição no texto original com acentos
        inicio = m.start(2)
        fim = m.end(2)
        descricao = texto_orig[inicio:fim].strip()
        descricao = " ".join(descricao.split())[:300]
        metas.append(MetaPactuada(numero=numero, descricao=descricao))
    return sorted(metas, key=lambda x: int(x.numero))


def _extrair_vocabulario(texto: str) -> list[str]:
    """Filtra quais termos do vocabulário-semente realmente aparecem no texto."""
    texto_lower = texto.lower()
    return [t for t in _VOCAB_SEED if t.lower() in texto_lower]


# ── ponto de entrada ─────────────────────────────────────────────────────────

def extrair_contexto_projeto(pdf: ProjetoPDFIndexado) -> ContextoProjeto:
    """
    Extrai o ContextoProjeto a partir do PDF do Termo de Outorga.

    Args:
        pdf: ProjetoPDFIndexado já carregado pelo pdf_reader existente.

    Returns:
        ContextoProjeto pronto para ser injetado no system prompt dos agentes.
    """
    texto_orig = pdf.texto_completo
    texto_norm = _norm(texto_orig)

    return ContextoProjeto(
        titulo_projeto=_extrair_titulo(texto_orig),
        financiador=_extrair_financiador(texto_orig),
        vigencia=_extrair_vigencia(texto_orig),
        objetivo_geral=_extrair_objetivo_geral(texto_norm, texto_orig),
        objetivos_especificos=_extrair_objetivos_especificos(texto_norm, texto_orig),
        metas_pactuadas=_extrair_metas(texto_norm, texto_orig),
        vocabulario_chave=_extrair_vocabulario(texto_orig),
    )

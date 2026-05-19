"""
Leitura e indexação do PDF institucional do projeto.

Responsabilidade: extrair texto do PDF e expor trechos por seção
para que o builder de contexto possa referenciar partes relevantes
sem misturar dado operacional (ClickUp) com conteúdo documental.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

try:
    import pypdf
except ImportError:
    pypdf = None  # type: ignore[misc, assignment]

_PYPDF_OK = pypdf is not None


# ── modelo de saída ───────────────────────────────────────────────────────────

@dataclass
class SecaoPDF:
    titulo:  str
    paginas: list[int]
    texto:   str


@dataclass
class ProjetoPDFIndexado:
    caminho:        Path
    total_paginas:  int
    texto_completo: str
    secoes:         list[SecaoPDF] = field(default_factory=list)

    def trecho(self, query: str, janela: int = 800) -> str:
        """
        Retorna o trecho mais relevante do PDF para uma query.
        Busca simples por palavra-chave — suficiente para contexto do writer.
        """
        texto = self.texto_completo.lower()
        q     = query.lower()
        idx   = texto.find(q)
        if idx == -1:
            # fallback: retorna início do documento
            return self.texto_completo[:janela].strip()
        inicio = max(0, idx - janela // 2)
        fim    = min(len(self.texto_completo), idx + janela // 2)
        return self.texto_completo[inicio:fim].strip()

    def secao(self, nome: str) -> Optional[SecaoPDF]:
        """Busca seção por nome parcial (case-insensitive)."""
        nome_lower = nome.lower()
        for s in self.secoes:
            if nome_lower in s.titulo.lower():
                return s
        return None


# ── títulos de seção que nos interessam ──────────────────────────────────────

_SECOES_ALVO = [
    "objeto",
    "objetivo",
    "meta",
    "atividade",
    "cronograma",
    "equipe",
    "orçamento",
    "resultado",
    "justificativa",
    "metodologia",
    "introdução",
    "resumo",
]

_RE_SECAO = re.compile(
    r"(?:^|\n)(\d+[\.\-]?\s*(?:" + "|".join(_SECOES_ALVO) + r")[^\n]{0,80})",
    re.IGNORECASE,
)


def _detectar_secoes(texto: str) -> list[SecaoPDF]:
    """Detecta seções no texto completo e retorna lista de SecaoPDF."""
    matches = list(_RE_SECAO.finditer(texto))
    secoes  = []
    for i, m in enumerate(matches):
        inicio = m.start()
        fim    = matches[i + 1].start() if i + 1 < len(matches) else len(texto)
        titulo = m.group(1).strip()
        trecho = texto[inicio:fim].strip()
        secoes.append(SecaoPDF(titulo=titulo, paginas=[], texto=trecho))
    return secoes


# ── função pública ────────────────────────────────────────────────────────────

def ler_pdf_projeto(caminho: Path) -> ProjetoPDFIndexado:
    """
    Lê o PDF do projeto e retorna um ProjetoPDFIndexado.

    Requer: pip install pypdf
    Se pypdf não estiver instalado, retorna objeto com texto vazio
    e loga aviso — não quebra o pipeline.
    """
    if not caminho.exists():
        raise FileNotFoundError(f"PDF do projeto não encontrado: {caminho}")

    if not _PYPDF_OK:
        import warnings
        warnings.warn(
            "pypdf não instalado. Instale com: pip install pypdf\n"
            "O contexto do PDF não estará disponível.",
            stacklevel=2,
        )
        return ProjetoPDFIndexado(
            caminho=caminho,
            total_paginas=0,
            texto_completo="",
        )

    assert pypdf is not None

    paginas_texto: list[str] = []
    with open(caminho, "rb") as f:
        reader = pypdf.PdfReader(f)
        for pagina in reader.pages:
            texto = pagina.extract_text() or ""
            paginas_texto.append(texto)

    texto_completo = "\n".join(paginas_texto)
    secoes         = _detectar_secoes(texto_completo)

    return ProjetoPDFIndexado(
        caminho=caminho,
        total_paginas=len(paginas_texto),
        texto_completo=texto_completo,
        secoes=secoes,
    )
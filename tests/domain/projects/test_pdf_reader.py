"""
Testes para app/domain/projects/pdf_reader.py

Rodar: pytest tests/domain/projects/test_pdf_reader.py -v
"""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.domain.projects.pdf_reader import (
    ProjetoPDFIndexado,
    SecaoPDF,
    _detectar_secoes,
    ler_pdf_projeto,
)


class TestDetectarSecoes:
    def test_detecta_objetivos(self):
        texto = "1. Objetivos do projeto\nDescrição dos objetivos aqui.\n2. Metodologia\nDescrição."
        secoes = _detectar_secoes(texto)
        assert any("objetivo" in s.titulo.lower() for s in secoes)

    def test_detecta_multiplas_secoes(self):
        texto = "1. Objetivos\nTexto A.\n2. Cronograma\nTexto B.\n3. Equipe\nTexto C."
        secoes = _detectar_secoes(texto)
        assert len(secoes) >= 2

    def test_texto_sem_secoes(self):
        texto = "Texto genérico sem títulos de seção reconhecíveis."
        secoes = _detectar_secoes(texto)
        assert secoes == []


class TestProjetoPDFIndexado:
    def _make(self, texto: str) -> ProjetoPDFIndexado:
        secoes = _detectar_secoes(texto)
        return ProjetoPDFIndexado(
            caminho=Path("fake.pdf"),
            total_paginas=1,
            texto_completo=texto,
            secoes=secoes,
        )

    def test_trecho_encontra_keyword(self):
        p = self._make("Texto antes. Objetivo principal é aprovar o projeto. Texto depois.")
        t = p.trecho("objetivo")
        assert "objetivo" in t.lower()

    def test_trecho_fallback_sem_match(self):
        p = self._make("Apenas um texto simples sem a palavra.")
        t = p.trecho("inexistente")
        assert len(t) > 0

    def test_secao_encontra_por_nome(self):
        p = self._make("1. Objetivos do projeto\nConteúdo.\n2. Cronograma\nDatas.")
        s = p.secao("objetivo")
        assert s is not None
        assert "objetivo" in s.titulo.lower()

    def test_secao_retorna_none_se_nao_encontrar(self):
        p = self._make("Texto sem seções.")
        assert p.secao("inexistente") is None


class TestLerPdfProjeto:
    def test_arquivo_nao_encontrado(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            ler_pdf_projeto(tmp_path / "nao_existe.pdf")

    def test_leitura_real_se_pypdf_disponivel(self, tmp_path):
        pytest.importorskip("pypdf")
        from app.core.config import PDF_PROJETO
        if not PDF_PROJETO.exists():
            pytest.skip("PDF do projeto não disponível em data/input/")
        resultado = ler_pdf_projeto(PDF_PROJETO)
        assert resultado.total_paginas > 0
        assert len(resultado.texto_completo) > 100
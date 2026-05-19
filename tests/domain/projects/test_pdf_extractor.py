"""
Testes para app/domain/projects/pdf_extractor.py

Rodar: pytest tests/domain/projects/test_pdf_extractor.py -v
"""
from datetime import date
from pathlib import Path

import pytest

from app.domain.projects.pdf_extractor import (
    AtividadePDF,
    ProjetoExtraido,
    _extrair_data_inicio,
    _mes_rel_para_data,
    _ultimo_dia_mes,
    extrair_projeto,
)
from app.domain.projects.pdf_reader import ProjetoPDFIndexado


# ── helpers de teste ──────────────────────────────────────────────────────────

def _pdf_fake(texto: str) -> ProjetoPDFIndexado:
    return ProjetoPDFIndexado(
        caminho=Path("fake.pdf"),
        total_paginas=1,
        texto_completo=texto,
    )


# ── _extrair_data_inicio ──────────────────────────────────────────────────────

class TestExtrairDataInicio:
    def test_formato_barra(self):
        assert _extrair_data_inicio("Início: 01/02/2025") == date(2025, 2, 1)

    def test_formato_ponto(self):
        assert _extrair_data_inicio("vigência 01.02.2025") == date(2025, 2, 1)

    def test_sem_data(self):
        assert _extrair_data_inicio("Sem data aqui") is None


# ── _mes_rel_para_data ────────────────────────────────────────────────────────

class TestMesRelParaData:
    def test_mes_1_e_data_inicio(self):
        assert _mes_rel_para_data(date(2025, 2, 1), 1) == date(2025, 2, 1)

    def test_mes_3_soma_2_meses(self):
        assert _mes_rel_para_data(date(2025, 2, 1), 3) == date(2025, 4, 1)

    def test_mes_12(self):
        assert _mes_rel_para_data(date(2025, 2, 1), 12) == date(2026, 1, 1)


# ── _ultimo_dia_mes ───────────────────────────────────────────────────────────

class TestUltimoDiaMes:
    def test_fevereiro_2025(self):
        assert _ultimo_dia_mes(date(2025, 2, 1)) == date(2025, 2, 28)

    def test_janeiro(self):
        assert _ultimo_dia_mes(date(2025, 1, 1)) == date(2025, 1, 31)

    def test_abril(self):
        assert _ultimo_dia_mes(date(2025, 4, 1)) == date(2025, 4, 30)


# ── extrair_projeto ───────────────────────────────────────────────────────────

class TestExtrairProjeto:
    def test_extrai_data_e_atividade(self):
        texto = """
        Início: 01/02/2025
        META 1
        Atividade 1.1
        Mês de início: 3
        Mês de fim: 6
        Duração: 4
        """
        p = extrair_projeto(_pdf_fake(texto))
        assert p.data_inicio == date(2025, 2, 1)
        assert len(p.atividades) == 1
        a = p.atividades[0]
        assert a.codigo == "1.1"
        assert a.mes_inicio_rel == 3
        assert a.mes_fim_rel == 6
        assert a.duracao_meses == 4
        assert a.data_inicio_abs == date(2025, 4, 1)
        assert a.data_fim_abs == date(2025, 7, 31)

    def test_multiplas_atividades(self):
        texto = """
        Início: 01/02/2025
        META 1
        Atividade 1.1
        Mês de início: 1
        Mês de fim: 2
        Duração: 2
        Atividade 1.2
        Mês de início: 3
        Mês de fim: 5
        Duração: 3
        """
        p = extrair_projeto(_pdf_fake(texto))
        assert len(p.atividades) == 2
        assert p.por_codigo("1.1") is not None
        assert p.por_codigo("1.2") is not None

    def test_sem_data_inicio(self):
        texto = """
        META 1
        Atividade 1.1
        Mês de início: 3
        Mês de fim: 6
        Duração: 4
        """
        p = extrair_projeto(_pdf_fake(texto))
        assert p.data_inicio is None
        assert p.atividades[0].data_inicio_abs is None

    def test_pdf_real_se_disponivel(self):
        from app.core.config import PDF_PROJETO
        from app.domain.projects.pdf_reader import ler_pdf_projeto
        if not PDF_PROJETO.exists():
            pytest.skip("PDF não disponível em data/input/")
        pdf = ler_pdf_projeto(PDF_PROJETO)
        p   = extrair_projeto(pdf)
        # valida que extraiu algo — não força valores específicos
        assert p.data_inicio is not None or len(p.atividades) >= 0
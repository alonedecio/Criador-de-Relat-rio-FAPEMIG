"""
Testes para app/domain/context/builder.py

Rodar: pytest tests/domain/context/test_builder.py -v
"""
from datetime import date
from typing import Optional

import pytest

from app.domain.clickup.models import ClickUpTaskBase, ClickUpTaskEnriched
from app.domain.projects.pdf_extractor import AtividadePDF
from app.domain.context.builders import montar_contexto, ContextoAtividade


# ── helpers ───────────────────────────────────────────────────────────────────

def _task(
    status="pendente",
    startdate: Optional[int] = None,
    duedate:   Optional[int] = None,
    descricao: str = "",
) -> ClickUpTaskEnriched:
    base = ClickUpTaskBase(
        id="t1", name="Teste", status=status,
        startdate=startdate, duedate=duedate,
    )
    return ClickUpTaskEnriched(
        task_id="t1", base=base,
        description=descricao,
    )


def _pdf_atv(
    mes_ini=3, mes_fim=6,
    dt_ini=date(2025, 4, 1),
    dt_fim=date(2025, 7, 31),
) -> AtividadePDF:
    return AtividadePDF(
        codigo="1.1", meta_codigo="1",
        mes_inicio_rel=mes_ini, mes_fim_rel=mes_fim,
        duracao_meses=mes_fim - mes_ini + 1,
        data_inicio_abs=dt_ini,
        data_fim_abs=dt_fim,
    )


# ── testes de prioridade de datas ─────────────────────────────────────────────

class TestPrioridadeDatas:
    def test_clickup_tem_prioridade_sobre_pdf(self):
        # ClickUp: abril→julho 2026 | PDF: abril→julho 2025
        task = _task(
            startdate=1_775_001_600_000,  # 01/04/2026
            duedate=1_785_456_000_000,    # 31/07/2026
        )
        pdf = _pdf_atv(dt_ini=date(2025, 4, 1), dt_fim=date(2025, 7, 31))
        ctx = montar_contexto("1.1", "Atividade teste", task, pdf)
        assert ctx.origem_datas == "clickup"
        assert ctx.data_inicio.year == 2026  # type: ignore

    def test_fallback_para_pdf_quando_clickup_sem_datas(self):
        task = _task()  # sem startdate/duedate
        pdf  = _pdf_atv(dt_ini=date(2025, 4, 1), dt_fim=date(2025, 7, 31))
        ctx  = montar_contexto("1.1", "Atividade teste", task, pdf)
        assert ctx.origem_datas == "pdf"
        assert ctx.data_inicio == date(2025, 4, 1)
        assert ctx.data_fim    == date(2025, 7, 31)

    def test_ausente_quando_nenhuma_fonte_tem_datas(self):
        ctx = montar_contexto("1.1", "Atividade teste", None, None)
        assert ctx.origem_datas == "ausente"
        assert ctx.data_inicio is None
        assert ctx.data_fim    is None


# ── testes de conteúdo ────────────────────────────────────────────────────────

class TestConteudo:
    def test_descricao_vinda_do_clickup(self):
        task = _task(descricao="Descrição detalhada da atividade.")
        ctx  = montar_contexto("1.1", "Título", task, None)
        assert ctx.descricao == "Descrição detalhada da atividade."

    def test_sem_task_campos_vazios(self):
        ctx = montar_contexto("1.1", "Título", None, None)
        assert ctx.descricao    == ""
        assert ctx.comentarios  == []
        assert ctx.responsaveis == []
        assert ctx.status       == "pendente"

    def test_meta_codigo_extraido_do_codigo(self):
        ctx = montar_contexto("3.2", "Título", None, None)
        assert ctx.meta_codigo == "3"


# ── testes de rastreabilidade ─────────────────────────────────────────────────

class TestRastreabilidade:
    def test_fontes_registradas(self):
        task = _task(startdate=1_743_465_600_000, duedate=1_753_920_000_000)
        ctx  = montar_contexto("1.1", "Título", task, None)
        campos = [f.campo for f in ctx.fontes]
        assert "data_inicio" in campos
        assert "data_fim"    in campos

    def test_origem_correta_nas_fontes(self):
        task = _task(startdate=1_743_465_600_000, duedate=1_753_920_000_000)
        ctx  = montar_contexto("1.1", "Título", task, None)
        for f in ctx.fontes:
            if f.campo in ("data_inicio", "data_fim"):
                assert f.origem == "clickup"


# ── teste de suficiência ──────────────────────────────────────────────────────

class TestSuficiencia:
    def test_tem_dados_suficientes(self):
        pdf = _pdf_atv()
        ctx = montar_contexto("1.1", "Título válido", None, pdf)
        assert ctx.tem_dados_suficientes() is True

    def test_sem_dados_suficientes(self):
        ctx = montar_contexto("1.1", "Título", None, None)
        assert ctx.tem_dados_suficientes() is False
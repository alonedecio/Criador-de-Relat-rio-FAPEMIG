"""
Testes para MontarContextosUseCase

Rodar: pytest tests/application/use_cases/test_montar_contextos.py -v
"""
from datetime import date

import pytest

from app.application.use_cases.montar_contextos import (
    EnrichedIndex,
    MontarContextosUseCase,
)
from app.domain.clickup.models import ClickUpTaskBase, ClickUpTaskEnriched
from app.domain.projects.pdf_extractor import AtividadePDF, ProjetoExtraido
from app.domain.reporting.canonical_schemas import (
    AtividadeCanonica,
    DatasCanonicas,
    MetaCanonica,
    ProgressoAtividadeCanonico,
    RelatorioCanonico,
    ResumoProjetoCanonico,
)


# ── helpers ─────────────────────────────────────────────────────────────────────

def _atv(codigo: str) -> AtividadeCanonica:
    return AtividadeCanonica(
        atividade_id=f"id_{codigo}",
        numero_atividade=codigo,
        numero_atividade_original=codigo,
        titulo=f"Atividade {codigo}",
        datas=DatasCanonicas(),
        progresso=ProgressoAtividadeCanonico(),
    )


def _meta(codigo: str, atividades: list[AtividadeCanonica]) -> MetaCanonica:
    return MetaCanonica(
        item=codigo,
        meta_id_original=f"meta_{codigo}",
        meta_nome=f"Meta {codigo}",
        atividades=atividades,
    )


def _relatorio(metas: list[MetaCanonica]) -> RelatorioCanonico:
    return RelatorioCanonico(
        metadata={"projeto": "teste"},
        resumo_projeto=ResumoProjetoCanonico(),
        metas=metas,
    )


def _task(codigo: str) -> ClickUpTaskEnriched:
    base = ClickUpTaskBase(
        id=f"t_{codigo}", name=f"Task {codigo}", status="em andamento",
        startdate=1_775_001_600_000,   # 01/04/2026
        duedate=1_785_456_000_000,     # 31/07/2026
    )
    return ClickUpTaskEnriched(task_id=f"t_{codigo}", base=base)


def _pdf_projeto(*codigos: str) -> ProjetoExtraido:
    atividades = [
        AtividadePDF(
            codigo=c, meta_codigo=c.split(".")[0],
            mes_inicio_rel=3, mes_fim_rel=6, duracao_meses=4,
            data_inicio_abs=date(2025, 4, 1),
            data_fim_abs=date(2025, 7, 31),
        )
        for c in codigos
    ]
    return ProjetoExtraido(data_inicio=date(2025, 2, 1), atividades=atividades)


# ── testes ───────────────────────────────────────────────────────────────────────

class TestMontarContextosUseCase:
    def setup_method(self):
        self.uc = MontarContextosUseCase()

    def test_monta_contexto_para_todas_atividades(self):
        relatorio = _relatorio([
            _meta("1", [_atv("1.1"), _atv("1.2")]),
            _meta("2", [_atv("2.1")]),
        ])
        resultado = self.uc.executar(relatorio, EnrichedIndex(), None)
        assert resultado.total == 3

    def test_conta_atividades_com_dados(self):
        relatorio = _relatorio([_meta("1", [_atv("1.1"), _atv("1.2")])])
        index     = EnrichedIndex({"1.1": _task("1.1")})
        pdf       = _pdf_projeto("1.1", "1.2")
        resultado = self.uc.executar(relatorio, index, pdf)
        assert resultado.com_dados == 2
        assert resultado.sem_dados == 0

    def test_atividade_sem_task_e_sem_pdf_vai_para_sem_dados(self):
        relatorio = _relatorio([_meta("1", [_atv("1.1")])])
        resultado = self.uc.executar(relatorio, EnrichedIndex(), None)
        assert resultado.sem_dados == 1
        assert "1.1" in resultado.codigos_sem_dados

    def test_clickup_tem_prioridade_sobre_pdf_nas_datas(self):
        relatorio = _relatorio([_meta("1", [_atv("1.1")])])
        index     = EnrichedIndex({"1.1": _task("1.1")})   # datas 2026
        pdf       = _pdf_projeto("1.1")                    # datas 2025
        resultado = self.uc.executar(relatorio, index, pdf)
        ctx = resultado.contextos[0]
        assert ctx.origem_datas == "clickup"
        assert ctx.data_inicio.year == 2026  # type: ignore

    def test_sem_pdf_usa_so_clickup(self):
        relatorio = _relatorio([_meta("1", [_atv("1.1")])])
        index     = EnrichedIndex({"1.1": _task("1.1")})
        resultado = self.uc.executar(relatorio, index, None)
        assert resultado.contextos[0].origem_datas == "clickup"

    def test_resumo_legivel(self):
        relatorio = _relatorio([_meta("1", [_atv("1.1")])])
        resultado = self.uc.executar(relatorio, EnrichedIndex(), None)
        assert "/" in resultado.resumo()

from datetime import datetime, timezone

from app.domain.reporting.canonical_schemas import (
    AtividadeCanonica,
    DatasCanonicas,
    MetaCanonica,
    ProgressoAtividadeCanonico,
    ProgressoMetaCanonico,
    RelatorioCanonico,
)
from app.services.enrichers.progress_enricher import enrich_report_progress


def _build_report(status: str, data_inicio=None, data_fim=None, data_fim_realizado=None):
    return RelatorioCanonico(
        metadata={"source": "test"},
        resumo_projeto={"dados": {}},
        metas=[
            MetaCanonica(
                item="1",
                meta_id_original="meta-1",
                meta_nome="Meta 1 - Teste",
                percentual_meta=None,
                atividades=[
                    AtividadeCanonica(
                        atividade_id="atv-1",
                        numero_atividade="1.1",
                        numero_atividade_original="1.1",
                        titulo_original="1.1 - Atividade teste",
                        titulo="Atividade teste",
                        indicador_fisico=None,
                        status_clickup=status,
                        percentual_realizado=None,
                        datas=DatasCanonicas(
                            data_inicio=data_inicio,
                            data_fim=data_fim,
                            data_fim_realizado=data_fim_realizado,
                        ),
                        progresso=ProgressoAtividadeCanonico(),
                        origem={},
                    )
                ],
                progresso=ProgressoMetaCanonico(),
            )
        ],
    )


def test_progress_enricher_marks_completed_activity_on_time():
    report = _build_report(
        status="concluído",
        data_inicio="2026-01-01T00:00:00+00:00",
        data_fim="2026-01-31T00:00:00+00:00",
        data_fim_realizado="2026-01-20T00:00:00+00:00",
    )

    out = enrich_report_progress(
        report,
        reference_datetime=datetime(2026, 1, 25, tzinfo=timezone.utc),
    )

    atividade = out.metas[0].atividades[0]
    assert atividade.progresso.realizado_percentual == 100.0
    assert atividade.progresso.situacao_prazo == "concluida_no_prazo"
    assert atividade.progresso.atrasada is False
    assert out.metas[0].progresso.realizado_percentual_medio == 100.0


def test_progress_enricher_marks_pending_activity_as_overdue():
    report = _build_report(
        status="pendente",
        data_inicio="2026-01-01T00:00:00+00:00",
        data_fim="2026-01-10T00:00:00+00:00",
        data_fim_realizado=None,
    )

    out = enrich_report_progress(
        report,
        reference_datetime=datetime(2026, 1, 20, tzinfo=timezone.utc),
    )

    atividade = out.metas[0].atividades[0]
    assert atividade.progresso.realizado_percentual == 0.0
    assert atividade.progresso.situacao_prazo == "nao_iniciada_atrasada"
    assert atividade.progresso.atrasada is True
    assert out.metas[0].progresso.realizado_percentual_medio == 0.0


def test_progress_enricher_uses_schedule_for_in_progress_activity():
    report = _build_report(
        status="em progresso",
        data_inicio="2026-01-01T00:00:00+00:00",
        data_fim="2026-01-11T00:00:00+00:00",
        data_fim_realizado=None,
    )

    out = enrich_report_progress(
        report,
        reference_datetime=datetime(2026, 1, 6, tzinfo=timezone.utc),
    )

    atividade = out.metas[0].atividades[0]
    assert atividade.progresso.previsto_percentual == 50.0
    assert atividade.progresso.realizado_percentual == 50.0
    assert atividade.progresso.situacao_prazo == "em_progresso_no_prazo"
    assert atividade.progresso.atrasada is False
    assert out.metas[0].progresso.previsto_percentual_medio == 50.0
    assert out.metas[0].progresso.realizado_percentual_medio == 50.0
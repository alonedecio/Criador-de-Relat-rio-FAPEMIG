"""
Testes para app/domain/reporting/progress.py

Rodar: pytest tests/domain/reporting/test_progress.py -v
"""
from datetime import datetime, timezone

from app.domain.clickup.models import ClickUpTaskBase, ClickUpTaskEnriched
from app.domain.reporting.progress import (
    _ms_to_mesano,
    _percentual_cronograma,
    _dias_entre,
    calcular_progresso,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _ts(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def _task(status: str, startdate=None, duedate=None, datedone=None):
    base = ClickUpTaskBase(
        id="t1", name="Teste", status=status,
        startdate=startdate, duedate=duedate, datedone=datedone,
    )
    return ClickUpTaskEnriched(task_id="t1", base=base)


# ── _ms_to_mesano ─────────────────────────────────────────────────────────────

class TestMsToMesano:
    def test_abril_2026(self):
        dt = datetime(2026, 4, 1, tzinfo=timezone.utc)
        assert _ms_to_mesano(_ts(dt)) == "042026"

    def test_fevereiro_2026(self):
        dt = datetime(2026, 2, 1, tzinfo=timezone.utc)
        assert _ms_to_mesano(_ts(dt)) == "022026"

    def test_none(self):
        assert _ms_to_mesano(None) is None


# ── _percentual_cronograma ────────────────────────────────────────────────────

class TestPercentualCronograma:
    def test_percentual_0(self):
        ini = datetime(2026, 2, 1, tzinfo=timezone.utc)
        fim = datetime(2026, 4, 1, tzinfo=timezone.utc)
        assert _percentual_cronograma(_ts(ini), _ts(fim), agora=ini) == 0.0

    def test_percentual_100(self):
        ini = datetime(2026, 2, 1, tzinfo=timezone.utc)
        fim = datetime(2026, 4, 1, tzinfo=timezone.utc)
        assert _percentual_cronograma(_ts(ini), _ts(fim), agora=fim) == 100.0

    def test_percentual_50(self):
        ini = datetime(2026, 1, 1, tzinfo=timezone.utc)
        fim = datetime(2026, 3, 1, tzinfo=timezone.utc)
        meio = ini + (fim - ini) / 2
        resultado = _percentual_cronograma(_ts(ini), _ts(fim), agora=meio)
        assert resultado is not None
        assert abs(resultado - 50.0) < 1.0

    def test_none_retorna_none(self):
        assert _percentual_cronograma(None, None) is None


# ── _dias_entre ───────────────────────────────────────────────────────────────

class TestDiasEntre:
    def test_25_dias(self):
        ini = datetime(2026, 2, 1, tzinfo=timezone.utc)
        fim = datetime(2026, 2, 26, tzinfo=timezone.utc)
        assert _dias_entre(_ts(ini), _ts(fim)) == 25

    def test_none(self):
        assert _dias_entre(None, None) is None


# ── calcular_progresso ────────────────────────────────────────────────────────

class TestCalcularProgresso:
    def test_concluida_no_prazo(self):
        ini = datetime(2026, 1, 1, tzinfo=timezone.utc)
        fim = datetime(2026, 2, 28, tzinfo=timezone.utc)
        feito = datetime(2026, 2, 15, tzinfo=timezone.utc)
        p = calcular_progresso(_task("concluído", _ts(ini), _ts(fim), _ts(feito)))
        assert p.realizado_percentual == 100.0
        assert p.atrasada is False
        assert p.situacao_prazo == "concluida_no_prazo"
        assert p.mes_ano_fim_real == "022026"

    def test_concluida_em_atraso(self):
        ini = datetime(2026, 1, 1, tzinfo=timezone.utc)
        fim = datetime(2026, 2, 1, tzinfo=timezone.utc)
        feito = datetime(2026, 3, 1, tzinfo=timezone.utc)
        p = calcular_progresso(_task("done", _ts(ini), _ts(fim), _ts(feito)))
        assert p.realizado_percentual == 100.0
        assert p.atrasada is True
        assert p.situacao_prazo == "concluida_em_atraso"

    def test_pendente_sem_datas(self):
        p = calcular_progresso(_task("pendente"))
        assert p.realizado_percentual == 0.0
        assert p.situacao_prazo == "nao_iniciada_sem_prazo"
        assert p.mes_ano_inicio_previsto is None

    def test_caso_real_comites_1_3(self):
        """Atividade 1.3 - Comitês: startdate=1777446000000, duedate=1780902000000."""
        p = calcular_progresso(_task("pendente", 1_777_446_000_000, 1_780_902_000_000))
        assert p.mes_ano_inicio_previsto == "042026"
        assert p.mes_ano_fim_previsto == "062026"
        assert p.duracao_prevista_dias == 40

    def test_caso_real_edital_mentores_7_2(self):
        """Atividade 7.2: startdate=1770188400000, duedate=1772348400000 → 25 dias."""
        p = calcular_progresso(_task("em progresso", 1_770_188_400_000, 1_772_348_400_000))
        assert p.mes_ano_inicio_previsto == "022026"
        assert p.mes_ano_fim_previsto == "032026"
        assert p.duracao_prevista_dias == 25
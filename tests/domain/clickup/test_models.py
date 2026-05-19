"""
Testes para app/domain/clickup/models.py

Rodar: pytest tests/domain/clickup/test_models.py -v
"""
from app.domain.clickup.models import (
    ClickUpTaskBase,
    ClickUpTaskEnriched,
    ClickUpEnrichedSnapshot,
)


def _task(startdate=None, duedate=None, datedone=None, dateclosed=None):
    base = ClickUpTaskBase(
        id="abc",
        name="Teste",
        status="pendente",
        startdate=startdate,
        duedate=duedate,
        datedone=datedone,
        dateclosed=dateclosed,
    )
    return ClickUpTaskEnriched(task_id="abc", base=base)


class TestProperties:
    def test_data_planejada_inicio(self):
        t = _task(startdate=1_770_188_400_000)
        assert t.data_planejada_inicio_ms == 1_770_188_400_000

    def test_data_planejada_fim(self):
        t = _task(duedate=1_780_902_000_000)
        assert t.data_planejada_fim_ms == 1_780_902_000_000

    def test_data_realizada_prefere_datedone(self):
        t = _task(datedone=111, dateclosed=222)
        assert t.data_realizada_fim_ms == 111

    def test_data_realizada_fallback_dateclosed(self):
        t = _task(dateclosed=999)
        assert t.data_realizada_fim_ms == 999

    def test_todas_nulas(self):
        t = _task()
        assert t.data_planejada_inicio_ms is None
        assert t.data_planejada_fim_ms is None
        assert t.data_realizada_fim_ms is None


class TestSnapshot:
    def test_index_vazio(self):
        snap = ClickUpEnrichedSnapshot()
        assert snap.index_by_id() == {}

    def test_index_com_duas_tasks(self):
        t1 = _task(); t1.task_id = "id-1"; t1.base.id = "id-1"
        t2 = _task(); t2.task_id = "id-2"; t2.base.id = "id-2"
        snap = ClickUpEnrichedSnapshot(tasks=[t1, t2])
        idx = snap.index_by_id()
        assert "id-1" in idx and "id-2" in idx
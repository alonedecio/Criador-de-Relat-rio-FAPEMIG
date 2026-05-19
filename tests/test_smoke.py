from app.core.config import DEFAULT_REPORT_FILE
from app.domain.reporting.assembler import ReportAssembler


def test_load_report():
    assembler = ReportAssembler()
    report = assembler.from_file(DEFAULT_REPORT_FILE)

    assert report.total_metas > 0
    assert report.total_atividades > 0
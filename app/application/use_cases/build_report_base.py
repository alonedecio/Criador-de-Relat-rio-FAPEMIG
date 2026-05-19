from pathlib import Path
from typing import Optional

from app.core.config import DEFAULT_REPORT_BASE_FILE
from app.application.use_cases.build_canonical_report import build_canonical_report
from app.services.exporters.report_base_exporter import export_report_base


def build_report_base(output_path: Optional[Path] = None) -> Path:
    report = build_canonical_report()
    final_output_path = output_path or DEFAULT_REPORT_BASE_FILE
    return export_report_base(report, final_output_path)
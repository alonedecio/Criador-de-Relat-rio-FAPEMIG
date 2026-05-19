from pathlib import Path
from typing import Optional

from app.core.config import DEFAULT_NORMALIZED_FILE
from app.application.use_cases.build_canonical_report import build_canonical_report
from app.services.exporters.canonical_exporter import export_canonical_report


def build_and_export_canonical_report(output_path: Optional[Path] = None) -> Path:
    report = build_canonical_report()
    final_output_path = output_path or DEFAULT_NORMALIZED_FILE
    return export_canonical_report(report, final_output_path)
from pathlib import Path
from typing import Optional

from app.core.config import DEFAULT_REPORT_FILE
from app.services.loaders.report_loader import load_raw_report
from app.domain.reporting.mapper import to_canonical_report
from app.domain.reporting.canonical_schemas import RelatorioCanonico


def build_canonical_report(path: Optional[Path] = None) -> RelatorioCanonico:
    report_path = path or DEFAULT_REPORT_FILE
    raw_data = load_raw_report(report_path)
    return to_canonical_report(raw_data)
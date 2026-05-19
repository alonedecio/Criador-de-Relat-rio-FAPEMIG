from pathlib import Path
from typing import Optional

from app.core.config import STAGED_DIR
from app.services.loaders.raw_clickup_loader import load_raw_clickup_payload
from app.domain.clickup.mapper import to_report_base_from_clickup
from app.services.exporters.report_base_from_clickup_exporter import export_report_base_from_clickup


DEFAULT_OUTPUT = STAGED_DIR / "report_base_from_clickup.json"


def build_report_base_from_clickup(output_path: Optional[Path] = None) -> Path:
    payload = load_raw_clickup_payload()
    report = to_report_base_from_clickup(payload)
    final_output_path = output_path or DEFAULT_OUTPUT
    return export_report_base_from_clickup(report, final_output_path)
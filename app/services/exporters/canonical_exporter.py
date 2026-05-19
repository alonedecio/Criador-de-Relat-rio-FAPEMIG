from pathlib import Path

from app.domain.reporting.canonical_schemas import RelatorioCanonico


def export_canonical_report(
    report: RelatorioCanonico,
    output_path: Path,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        report.model_dump_json(indent=2),
        encoding="utf-8",
    )
    return output_path
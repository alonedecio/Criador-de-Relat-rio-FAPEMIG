import json
from pathlib import Path

from app.domain.reporting.schemas import RelatorioProjeto


class ReportAssembler:
    def from_file(self, file_path: str | Path) -> RelatorioProjeto:
        path = Path(file_path)
        with path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
        return self.from_dict(payload)

    def from_dict(self, payload: dict) -> RelatorioProjeto:
        return RelatorioProjeto.model_validate(payload)
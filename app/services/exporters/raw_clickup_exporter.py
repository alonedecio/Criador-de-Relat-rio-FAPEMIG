import json
from pathlib import Path


def export_raw_clickup_payload(payload: dict, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    return output_path
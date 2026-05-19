from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def export_clickup_base_snapshot(payload: dict[str, Any], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as fp:
        json.dump(payload, fp, ensure_ascii=False, indent=2)

    return output_path
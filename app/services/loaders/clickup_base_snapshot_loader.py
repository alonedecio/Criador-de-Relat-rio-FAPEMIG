from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_clickup_base_snapshot(input_path: Path) -> dict[str, Any]:
    with input_path.open("r", encoding="utf-8") as fp:
        return json.load(fp)
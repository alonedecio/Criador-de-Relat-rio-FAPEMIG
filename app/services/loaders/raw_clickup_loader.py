import json
from pathlib import Path
from typing import Any, Dict

from app.core.config import DEFAULT_CLICKUP_RAW_FILE


def load_raw_clickup_payload(path: Path = DEFAULT_CLICKUP_RAW_FILE) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)
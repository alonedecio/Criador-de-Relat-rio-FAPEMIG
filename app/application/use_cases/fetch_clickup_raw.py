from pathlib import Path
from typing import Optional

from app.core.config import (
    CLICKUP_API_TOKEN,
    CLICKUP_SPACE_ID,
    CLICKUP_FOLDER_ID,
    CLICKUP_LIST_ID,
    DEFAULT_CLICKUP_RAW_FILE,
)
from app.domain.clickup.client import ClickUpClient
from app.domain.clickup.service import ClickUpIngestionService
from app.services.exporters.raw_clickup_exporter import export_raw_clickup_payload


def fetch_clickup_raw(output_path: Optional[Path] = None) -> Path:
    if not CLICKUP_API_TOKEN:
        raise ValueError("CLICKUP_API_TOKEN não definido no ambiente.")

    if not CLICKUP_LIST_ID:
        raise ValueError("CLICKUP_LIST_ID não definido no ambiente.")

    client = ClickUpClient(api_token=CLICKUP_API_TOKEN)
    service = ClickUpIngestionService(client)

    payload = service.fetch_full_payload(
        space_id=CLICKUP_SPACE_ID,
        folder_id=CLICKUP_FOLDER_ID,
        list_id=CLICKUP_LIST_ID,
    )

    final_output_path = output_path or DEFAULT_CLICKUP_RAW_FILE
    return export_raw_clickup_payload(payload, final_output_path)
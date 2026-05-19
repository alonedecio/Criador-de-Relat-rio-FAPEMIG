from pathlib import Path
import os

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[2]

ENV_FILE = BASE_DIR / ".env"

load_dotenv(ENV_FILE)


DATA_DIR = BASE_DIR / "data"
INPUT_DIR = DATA_DIR / "input"
STAGED_DIR = DATA_DIR / "staged"

DEFAULT_REPORT_FILE = INPUT_DIR / "relatorio_com_progresso_clickup_api.json"

TEMPLATES_DIR = BASE_DIR / "app" / "domain" / "rendering" / "templates"
RAW_DIR = DATA_DIR / "raw"
NORMALIZED_DIR = DATA_DIR / "normalized"


DEFAULT_NORMALIZED_FILE = NORMALIZED_DIR / "relatorio_canonico.json"


DEFAULT_REPORT_BASE_FILE = STAGED_DIR / "report_base.json"
DEFAULT_CLICKUP_RAW_FILE = RAW_DIR / "clickup_full_payload.json"


CLICKUP_API_TOKEN = os.getenv("CLICKUP_API_TOKEN")
CLICKUP_TEAM_ID = os.getenv("CLICKUP_TEAM_ID")
CLICKUP_SPACE_ID = os.getenv("CLICKUP_SPACE_ID")
CLICKUP_FOLDER_ID = os.getenv("CLICKUP_FOLDER_ID")
CLICKUP_LIST_ID = os.getenv("CLICKUP_LIST_ID")
CLICKUP_API_BASE = "https://api.clickup.com/api/v2"


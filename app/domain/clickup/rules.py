# app/domain/clickup/rules.py
import re
from typing import Optional

META_PATTERN = re.compile(r"^Meta\s+(\d+)\s*-\s*(.+)$", re.IGNORECASE)
ATIVIDADE_PATTERN = re.compile(r"^(\d+)\.(\d+)\s*-\s*(.+)$")

def parse_meta_name(name: Optional[str]) -> Optional[dict]:
    if not name:
        return None
    m = META_PATTERN.match(name.strip())
    if not m:
        return None
    return {
        "meta_numero": int(m.group(1)),
        "meta_titulo": m.group(2).strip(),
    }

def parse_activity_name(name: Optional[str]) -> Optional[dict]:
    if not name:
        return None
    m = ATIVIDADE_PATTERN.match(name.strip())
    if not m:
        return None
    return {
        "meta_numero": int(m.group(1)),
        "atividade_numero": int(m.group(2)),
        "titulo": m.group(3).strip(),
        "numero_original": f"{m.group(1)}.{m.group(2)}",
    }

def is_valid_meta_name(name: Optional[str]) -> bool:
    return parse_meta_name(name) is not None

def is_valid_activity_name(name: Optional[str]) -> bool:
    return parse_activity_name(name) is not None
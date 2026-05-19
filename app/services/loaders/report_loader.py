import json
from pathlib import Path
from typing import Any, Dict

from app.core.config import DEFAULT_REPORT_FILE


def load_raw_report(path: Path = DEFAULT_REPORT_FILE) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def extract_cronograma_section(data: Dict[str, Any]) -> Dict[str, Any]:
    return (
        data.get("relatorio", {})
        .get("secoes_fixas", {})
        .get("3_tabela_resumo_execucao_cronograma_fisico", {})
    )


def extract_items_meta_atividade(data: Dict[str, Any]) -> list:
    secao = extract_cronograma_section(data)
    return secao.get("itens_meta_atividade", [])


def extract_metadata(data: Dict[str, Any]) -> Dict[str, Any]:
    return data.get("relatorio", {}).get("metadata", {})
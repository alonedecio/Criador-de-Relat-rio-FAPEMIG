"""Use case: gera o HTML do relatório a partir do JSON canônico.

Fluxo:
  1. Carrega o JSON canônico (com ou sem textos de IA já aplicados)
  2. Delega a renderização ao HtmlRenderer
  3. Salva o arquivo HTML no output_path

Uso direto (sem CLI):
    from app.application.use_cases.gerar_html_relatorio import executar
    executar(relatorio_path=Path(...), output_path=Path(...))
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from app.domain.rendering.html_renderer import salvar_html

logger = logging.getLogger(__name__)


def executar(
    relatorio_path: Path,
    output_path: Path,
) -> Path:
    """Carrega o JSON canônico e gera o HTML do relatório.

    Args:
        relatorio_path: caminho para o JSON canônico
                        (relatorio_final_completo.json ou teste_textos_parcial.json)
        output_path:    caminho onde o HTML será salvo

    Returns:
        Path do arquivo HTML gerado.
    """
    logger.info("Carregando relatório: %s", relatorio_path)
    with open(relatorio_path, "r", encoding="utf-8") as f:
        relatorio = json.load(f)

    n_metas = len(relatorio.get("metas", []))
    n_atividades = sum(
        len(m.get("atividades", [])) for m in relatorio.get("metas", [])
    )
    logger.info("JSON carregado: %d meta(s), %d atividade(s)", n_metas, n_atividades)

    path = salvar_html(relatorio, output_path)
    logger.info("HTML salvo em: %s", path)
    return path

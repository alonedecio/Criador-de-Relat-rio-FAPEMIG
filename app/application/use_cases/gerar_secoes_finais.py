"""
Use Case: Gerar textos das seções finais do RAT (seções 5 a 10).

Deve ser executado APÓS gerar_textos_atividades, pois usa o relatório
com os textos das atividades já aplicados como contexto adicional.

Fluxo:
    1. Carrega o relatório com textos (output de gerar_textos_atividades)
    2. Carrega o Termo de Outorga (PDF) para contexto de projeto
    3. Executa writer_secoes_finais (1 chamada LLM)
    4. Aplica os textos no relatório e salva
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def executar(
    termo_pdf_path: Path,
    relatorio_com_textos_path: Path,
    output_path: Path,
    llm_client,
    model: str = "gemini-2.5-flash-lite",
) -> dict:
    """
    Gera os textos das seções finais e os aplica no relatório.

    Args:
        termo_pdf_path:            Path para o PDF do Termo de Outorga.
        relatorio_com_textos_path: Path para o JSON com textos das atividades.
        output_path:               Path para salvar o relatório final completo.
        llm_client:                Cliente openai.OpenAI.
        model:                     Modelo LLM.

    Returns:
        Relatório completo com textos de atividades + seções finais.
    """
    # 1. Carrega o Termo de Outorga
    from app.domain.projects.pdf_reader import ler_pdf_projeto
    from app.domain.projects.termo_outorga import extrair_contexto_projeto

    logger.info("Carregando Termo de Outorga: %s", termo_pdf_path)
    pdf_indexado = ler_pdf_projeto(termo_pdf_path)
    ctx_projeto = extrair_contexto_projeto(pdf_indexado)
    logger.info(
        "ContextoProjeto: '%s' | %d metas",
        ctx_projeto.titulo_projeto[:60],
        len(ctx_projeto.metas_pactuadas),
    )

    # 2. Carrega relatório com textos das atividades
    logger.info("Carregando relatório com textos: %s", relatorio_com_textos_path)
    with open(relatorio_com_textos_path, "r", encoding="utf-8") as f:
        relatorio = json.load(f)

    # 3. Enriquece atividades com indicador físico do PDF
    from app.domain.projects.indicador_fisico import enriquecer_atividades_com_indicador

    pdf_texto = pdf_indexado.texto_completo if hasattr(pdf_indexado, "texto_completo") else ""
    if pdf_texto:
        relatorio = enriquecer_atividades_com_indicador(relatorio, pdf_texto)
        logger.info("Indicadores físicos extraídos do PDF.")
    else:
        logger.warning(
            "Texto do PDF não disponível — indicadores físicos não serão extraídos."
        )

    # 4. Executa writer das seções finais
    from app.domain.ai.writer_secoes_finais import gerar_secoes_finais

    textos_finais = gerar_secoes_finais(
        ctx_projeto=ctx_projeto,
        relatorio_com_textos=relatorio,
        llm_client=llm_client,
        model=model,
    )

    # 5. Aplica os textos no relatório
    secoes = relatorio.setdefault("secoes_finais", {})
    secoes["capacitacoes_equipe"]       = textos_finais.capacitacoes_equipe
    secoes["melhorias_instalacoes"]     = textos_finais.melhorias_instalacoes
    secoes["dificuldades_nao_tecnicas"] = textos_finais.dificuldades_nao_tecnicas
    secoes["impactos_internos"]         = textos_finais.impactos_internos
    secoes["impactos_externos"]         = textos_finais.impactos_externos
    secoes["producao_tecnologica"]      = textos_finais.producao_tecnologica
    secoes["parcerias_institucionais"]  = textos_finais.parcerias_institucionais
    secoes["comentario_final"]          = textos_finais.comentario_final
    secoes["resumo"]                    = textos_finais.resumo

    # 6. Salva
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(relatorio, f, ensure_ascii=False, indent=2)

    logger.info("Relatório completo salvo em: %s", output_path)
    return relatorio

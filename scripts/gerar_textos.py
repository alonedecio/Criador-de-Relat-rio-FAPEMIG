"""
Script CLI para executar o pipeline de geração de textos.

Uso:
    python scripts/gerar_textos.py
    python scripts/gerar_textos.py --atividades 4.2 7.1 13.1   # processa só estas
    python scripts/gerar_textos.py --model gpt-4o-mini          # modelo mais barato para teste

Variáveis de ambiente necessárias:
    OPENAI_API_KEY  — chave da OpenAI

Caminhos default (configuráveis via argumentos):
    Termo PDF:      data/input/termo_projeto.pdf
    Relatório:      output/relatorio_com_progresso_clickup_api.json
    Snapshot:       output/clickup_enriched_snapshot.json
    Saída:          output/relatorio_com_textos.json
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Garante que o root do projeto está no path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("gerar_textos")


def main():
    parser = argparse.ArgumentParser(description="Gera textos das atividades via agentes IA.")
    parser.add_argument(
        "--termo",
        type=Path,
        default=Path("data/input/termo_projeto.pdf"),
        help="Caminho para o PDF do Termo de Outorga",
    )
    parser.add_argument(
        "--relatorio",
        type=Path,
        default=Path("output/relatorio_com_progresso_clickup_api.json"),
        help="Caminho para o JSON de relatório com progresso",
    )
    parser.add_argument(
        "--snapshot",
        type=Path,
        default=Path("output/clickup_enriched_snapshot.json"),
        help="Caminho para o snapshot enriquecido do ClickUp",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output/relatorio_com_textos.json"),
        help="Caminho de saída do relatório final",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-4o",
        help="Modelo LLM (ex: gpt-4o, gpt-4o-mini)",
    )
    parser.add_argument(
        "--tentativas",
        type=int,
        default=3,
        help="Número máximo de tentativas por atividade",
    )
    parser.add_argument(
        "--atividades",
        nargs="+",
        default=None,
        help="Filtro de atividades (ex: 4.2 7.1). Omitir = processa todas.",
    )
    args = parser.parse_args()

    # Valida entradas
    for path, nome in [
        (args.termo,     "Termo PDF"),
        (args.relatorio, "Relatório de progresso"),
        (args.snapshot,  "Snapshot ClickUp"),
    ]:
        if not path.exists():
            logger.error("%s não encontrado: %s", nome, path)
            sys.exit(1)

    # Inicializa cliente LLM
    try:
        import openai
        client = openai.OpenAI()
    except ImportError:
        logger.error("openai não instalado. Execute: pip install openai")
        sys.exit(1)

    # Executa
    from app.application.use_cases.gerar_textos_atividades import executar

    relatorio_final = executar(
        termo_pdf_path=args.termo,
        relatorio_progresso_path=args.relatorio,
        clickup_snapshot_path=args.snapshot,
        output_path=args.output,
        llm_client=client,
        model=args.model,
        max_tentativas=args.tentativas,
        atividades_filtro=args.atividades,
    )

    total_atividades = sum(
        len(item.get("atividades", []))
        for item in relatorio_final.get("itens", [])
    )
    logger.info("Pipeline concluído. %d atividades no relatório final.", total_atividades)
    logger.info("Resultado salvo em: %s", args.output)


if __name__ == "__main__":
    main()

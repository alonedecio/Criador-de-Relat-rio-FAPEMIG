"""
Script de geração do HTML do relatório de acompanhamento técnico.

Uso:
    # Usar o JSON principal (com todos os textos gerados)
    python scripts/gerar_html.py

    # Usar o JSON parcial de teste (subset de atividades)
    python scripts/gerar_html.py --relatorio data/output/teste_textos_parcial.json

    # Especificar destino customizado
    python scripts/gerar_html.py --output data/output/meu_relatorio.html

Saída padrão:
    data/output/relatorio_acompanhamento.html
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("gerar_html")

DATA_OUTPUT = ROOT / "data" / "output"
RELATORIO_DEFAULT = DATA_OUTPUT / "relatorio_final_completo.json"
OUTPUT_DEFAULT = DATA_OUTPUT / "relatorio_acompanhamento.html"

SEP = "\u2501" * 70


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Gera o HTML do relatório de acompanhamento técnico."
    )
    parser.add_argument(
        "--relatorio", "-r",
        default=str(RELATORIO_DEFAULT),
        help=f"JSON canônico de entrada (padrão: {RELATORIO_DEFAULT.relative_to(ROOT)})",
    )
    parser.add_argument(
        "--output", "-o",
        default=str(OUTPUT_DEFAULT),
        help=f"Caminho de saída do HTML (padrão: {OUTPUT_DEFAULT.relative_to(ROOT)})",
    )
    args = parser.parse_args()

    relatorio_path = Path(args.relatorio)
    output_path = Path(args.output)

    if not relatorio_path.exists():
        logger.error("Arquivo não encontrado: %s", relatorio_path)
        sys.exit(1)

    print(SEP)
    print(f"  Gerador de HTML — Relatório de Acompanhamento Técnico")
    print(f"  Entrada : {relatorio_path.name}")
    print(f"  Saída   : {output_path}")
    print(SEP)

    from app.application.use_cases.gerar_html_relatorio import executar

    html_path = executar(
        relatorio_path=relatorio_path,
        output_path=output_path,
    )

    print(f"\n✅ HTML gerado em: {html_path}")
    print(f"   Para abrir: start {html_path}\n")


if __name__ == "__main__":
    main()

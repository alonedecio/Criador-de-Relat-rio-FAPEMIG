"""
Script CLI para executar SOMENTE a etapa de geração de textos (etapa 4).

Pré-requisito: rodar as etapas 1-3 antes (ou usar pipeline_completo.py).

Uso:
    python scripts/gerar_textos.py
    python scripts/gerar_textos.py --atividades 2.1 4.1 6.1 16.1
    python scripts/gerar_textos.py --model gemini/gemini-2.0-flash

Variáveis de ambiente (.env):
    GEMINI_API_KEY  — chave da Google AI (Gemini)
    OPENAI_API_KEY  — alternativa OpenAI

Caminhos default:
    Termo PDF:      data/input/termo_projeto.pdf
    Relatório:      data/output/relatorio_final_com_progresso.json
    Snapshot:       data/staged/clickup_enriched_snapshot.json
    Saída:          data/output/relatorio_com_textos.json
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("gerar_textos")

BASE_DIR = Path(__file__).resolve().parent.parent


def _build_llm_client(model: str):
    use_gemini = model.startswith("gemini/") or bool(os.getenv("GEMINI_API_KEY"))
    use_openai = model.startswith("gpt-") or bool(os.getenv("OPENAI_API_KEY"))

    if use_gemini and not use_openai:
        try:
            import litellm
            litellm.set_verbose = False

            class _LiteLLMWrapper:
                def __init__(self, api_key: str):
                    os.environ["GEMINI_API_KEY"] = api_key

                class _Completions:
                    @staticmethod
                    def create(**kwargs):
                        import litellm as _ll
                        return _ll.completion(**kwargs)

                class _Chat:
                    completions = _Completions()

                chat = _Chat()

            gemini_key = os.getenv("GEMINI_API_KEY", "")
            if not gemini_key:
                logger.error("GEMINI_API_KEY não encontrada no .env")
                sys.exit(1)

            logger.info("LLM client: LiteLLM → %s", model)
            return _LiteLLMWrapper(gemini_key)

        except ImportError:
            logger.error("litellm não instalado. Execute: pip install litellm")
            sys.exit(1)

    try:
        import openai
        logger.info("LLM client: openai.OpenAI → %s", model)
        return openai.OpenAI()
    except ImportError:
        logger.error("openai não instalado. Execute: pip install openai")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Gera textos das atividades via agentes IA.")
    parser.add_argument(
        "--termo",
        type=Path,
        default=BASE_DIR / "data" / "input" / "termo_projeto.pdf",
    )
    parser.add_argument(
        "--relatorio",
        type=Path,
        default=BASE_DIR / "data" / "output" / "relatorio_final_com_progresso.json",
    )
    parser.add_argument(
        "--snapshot",
        type=Path,
        default=BASE_DIR / "data" / "staged" / "clickup_enriched_snapshot.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=BASE_DIR / "data" / "output" / "relatorio_com_textos.json",
    )
    parser.add_argument("--model", type=str, default="gemini/gemini-2.0-flash")
    parser.add_argument("--tentativas", type=int, default=3)
    parser.add_argument("--atividades", nargs="+", default=None)
    args = parser.parse_args()

    for path, nome in [
        (args.termo,     "Termo PDF"),
        (args.relatorio, "Relatório de progresso"),
        (args.snapshot,  "Snapshot ClickUp"),
    ]:
        if not path.exists():
            logger.error("%s não encontrado: %s", nome, path)
            sys.exit(1)

    client = _build_llm_client(args.model)

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

    total = sum(
        len(item.get("atividades", []))
        for item in relatorio_final.get("itens", [])
    )
    logger.info("Pipeline concluído. %d atividades no relatório final.", total)
    logger.info("Resultado salvo em: %s", args.output)


if __name__ == "__main__":
    main()

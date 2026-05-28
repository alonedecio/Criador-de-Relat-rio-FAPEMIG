"""
Script CLI para executar o pipeline de geração de textos.

Uso:
    python scripts/gerar_textos.py
    python scripts/gerar_textos.py --atividades 2.1 4.1 6.1 16.1
    python scripts/gerar_textos.py --model gemini/gemini-2.0-flash

Variáveis de ambiente necessárias (.env):
    GEMINI_API_KEY  — chave da Google AI (Gemini)

    Alternativa OpenAI:
    OPENAI_API_KEY  — chave da OpenAI (usa gpt-4o por padrão)

Caminhos default (configuráveis via argumentos):
    Termo PDF:      data/input/termo_projeto.pdf
    Relatório:      output/relatorio_com_progresso_clickup_api.json
    Snapshot:       output/clickup_enriched_snapshot.json
    Saída:          output/relatorio_com_textos.json
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

# Garante que o root do projeto está no path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Carrega .env antes de qualquer import de domínio
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("gerar_textos")


def _build_llm_client(model: str):
    """
    Instancia o cliente LLM correto com base no modelo informado e nas
    variáveis de ambiente disponíveis.

    Estratégia de detecção:
        - modelo começa com 'gemini/'  → LiteLLM com GEMINI_API_KEY
        - modelo começa com 'gpt-' ou OPENAI_API_KEY presente → openai.OpenAI()
        - fallback                     → LiteLLM (suporta qualquer provider)
    """
    use_gemini = model.startswith("gemini/") or bool(os.getenv("GEMINI_API_KEY"))
    use_openai = model.startswith("gpt-") or bool(os.getenv("OPENAI_API_KEY"))

    if use_gemini and not use_openai:
        try:
            from litellm import OpenAI as LiteLLMClient  # noqa: F401
        except ImportError:
            pass

        # LiteLLM expõe interface 100% compatível com openai.OpenAI
        try:
            import litellm
            litellm.set_verbose = False

            # Wrapper leve: retorna objeto com .chat.completions.create
            class _LiteLLMWrapper:
                """Wrapper mínimo para compatibilidade com writer/validator."""

                def __init__(self, api_key: str):
                    self._api_key = api_key
                    os.environ["GEMINI_API_KEY"] = api_key

                class _Completions:
                    @staticmethod
                    def create(**kwargs):
                        import litellm as _ll
                        return _ll.completion(**kwargs)

                class _Chat:
                    completions = _LiteLLMWrapper._Completions()

                chat = _Chat()

            gemini_key = os.getenv("GEMINI_API_KEY", "")
            if not gemini_key:
                logger.error("GEMINI_API_KEY não encontrada no .env")
                sys.exit(1)

            logger.info("Cliente LLM: LiteLLM → %s", model)
            return _LiteLLMWrapper(gemini_key)

        except ImportError:
            logger.error(
                "litellm não instalado. Execute: pip install litellm\n"
                "Ou use OpenAI: defina OPENAI_API_KEY no .env e passe --model gpt-4o"
            )
            sys.exit(1)

    # OpenAI
    try:
        import openai
        logger.info("Cliente LLM: openai.OpenAI → %s", model)
        return openai.OpenAI()
    except ImportError:
        logger.error("openai não instalado. Execute: pip install openai")
        sys.exit(1)


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
        default="gemini/gemini-2.0-flash",
        help="Modelo LLM (ex: gemini/gemini-2.0-flash, gemini/gemini-1.5-pro, gpt-4o)",
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
        help="Filtro de atividades (ex: 2.1 4.1 6.1 16.1). Omitir = processa todas.",
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

    total_atividades = sum(
        len(item.get("atividades", []))
        for item in relatorio_final.get("itens", [])
    )
    logger.info("Pipeline concluído. %d atividades no relatório final.", total_atividades)
    logger.info("Resultado salvo em: %s", args.output)


if __name__ == "__main__":
    main()

"""
Pipeline completo de geração de relatório com textos.

Etapas:
    1. Busca tasks do ClickUp e salva base snapshot
       → data/staged/clickup_base_snapshot.json

    2. Enriquece cada task (comentários, anexos, checklists)
       → data/staged/clickup_enriched_snapshot.json

    3. Gera relatório canônico com progresso
       → data/output/relatorio_final_com_progresso.json

    4. Agentes IA geram textos por atividade (writer → validator → retry)
       → data/output/relatorio_com_textos.json

Uso:
    # Pipeline completo
    python scripts/pipeline_completo.py

    # Só a partir da etapa 3 (snapshot já existe)
    python scripts/pipeline_completo.py --etapa-inicio 3

    # Só agentes, limitado a 4 atividades de teste
    python scripts/pipeline_completo.py --etapa-inicio 4 --atividades 2.1 4.1 6.1 16.1

    # Modelo específico
    python scripts/pipeline_completo.py --etapa-inicio 4 --atividades 2.1 4.1 --model gemini/gemini-2.5-flash-preview-05-20

Variáveis de ambiente (.env):
    CLICKUP_API_TOKEN   — obrigatório para etapas 1 e 2
    CLICKUP_LIST_ID     — obrigatório para etapa 1
    GEMINI_API_KEY      — obrigatório para etapa 4
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path

# root do projeto no path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("pipeline_completo")

# Modelo Gemini padrão — atualizar aqui quando mudar de versão
DEFAULT_MODEL = "gemini/gemini-2.5-flash-preview-05-20"

# ── paths canônicos ────────────────────────────────────────────────────────────
BASE_DIR      = Path(__file__).resolve().parent.parent
STAGED_DIR    = BASE_DIR / "data" / "staged"
INPUT_DIR     = BASE_DIR / "data" / "input"
OUTPUT_DIR    = BASE_DIR / "data" / "output"

BASE_SNAPSHOT     = STAGED_DIR / "clickup_base_snapshot.json"
ENRICHED_SNAPSHOT = STAGED_DIR / "clickup_enriched_snapshot.json"
RELATORIO_PROG    = OUTPUT_DIR / "relatorio_final_com_progresso.json"
RELATORIO_TEXTOS  = OUTPUT_DIR / "relatorio_com_textos.json"
PDF_PROJETO       = INPUT_DIR  / "termo_projeto.pdf"


# ── LiteLLM wrapper (nível de módulo para evitar NameError de escopo) ──────────

def _litellm_completion(**kwargs):
    """Chama litellm.completion — função separada para poder ser referenciada."""
    import litellm as _ll
    return _ll.completion(**kwargs)


class _LiteLLMChat:
    """Imita openai.OpenAI().chat com interface .completions.create()."""

    class _Completions:
        @staticmethod
        def create(**kwargs):
            return _litellm_completion(**kwargs)

    completions = _Completions()


class _LiteLLMClient:
    """
    Wrapper mínimo compatível com a interface openai.OpenAI usada no
    writer e validator:  client.chat.completions.create(...)
    """

    def __init__(self, api_key: str) -> None:
        os.environ["GEMINI_API_KEY"] = api_key
        self.chat = _LiteLLMChat()


# ── helpers ────────────────────────────────────────────────────────────────────

def _sep(titulo: str) -> None:
    logger.info("")
    logger.info("━" * 60)
    logger.info("  %s", titulo)
    logger.info("━" * 60)


def _build_llm_client(model: str):
    """Instancia cliente LLM: LiteLLM/Gemini ou openai.OpenAI."""
    use_gemini = model.startswith("gemini/") or bool(os.getenv("GEMINI_API_KEY"))
    use_openai = model.startswith("gpt-") or bool(os.getenv("OPENAI_API_KEY"))

    if use_gemini and not use_openai:
        try:
            import litellm
            litellm.set_verbose = False
        except ImportError:
            logger.error(
                "litellm não instalado.\n"
                "Execute: pip install litellm"
            )
            sys.exit(1)

        gemini_key = os.getenv("GEMINI_API_KEY", "")
        if not gemini_key:
            logger.error("GEMINI_API_KEY não encontrada no .env")
            sys.exit(1)

        logger.info("LLM client: LiteLLM → %s", model)
        return _LiteLLMClient(gemini_key)

    try:
        import openai
        logger.info("LLM client: openai.OpenAI → %s", model)
        return openai.OpenAI()
    except ImportError:
        logger.error("openai não instalado. Execute: pip install openai")
        sys.exit(1)


# ── etapas ─────────────────────────────────────────────────────────────────────

def etapa_1_base_snapshot() -> None:
    _sep("ETAPA 1 — Buscar tasks do ClickUp (base snapshot)")
    from app.application.use_cases.build_clickup_base_snapshot import build_clickup_base_snapshot
    STAGED_DIR.mkdir(parents=True, exist_ok=True)
    saida = build_clickup_base_snapshot(output_path=BASE_SNAPSHOT)
    logger.info("Base snapshot salvo em: %s", saida)


def etapa_2_enriched_snapshot() -> None:
    _sep("ETAPA 2 — Enriquecer tasks (comentários, anexos, checklists)")
    if not BASE_SNAPSHOT.exists():
        logger.error("Base snapshot não encontrado: %s\nRode a etapa 1 primeiro.", BASE_SNAPSHOT)
        sys.exit(1)
    from app.application.use_cases.build_clickup_enriched_snapshot import build_clickup_enriched_snapshot
    saida = build_clickup_enriched_snapshot(
        input_path=BASE_SNAPSHOT,
        output_path=ENRICHED_SNAPSHOT,
    )
    logger.info("Enriched snapshot salvo em: %s", saida)


def etapa_3_relatorio_progresso() -> None:
    _sep("ETAPA 3 — Gerar relatório canônico com progresso")
    if not ENRICHED_SNAPSHOT.exists():
        logger.error("Enriched snapshot não encontrado: %s\nRode a etapa 2 primeiro.", ENRICHED_SNAPSHOT)
        sys.exit(1)

    import json
    import re
    from app.domain.clickup.mapper import to_report_base_from_clickup
    from app.domain.clickup.models import ClickUpEnrichedSnapshot, ClickUpTaskEnriched
    from app.domain.projects.pdf_reader import ler_pdf_projeto
    from app.domain.projects.pdf_extractor import extrair_projeto
    from app.application.use_cases.montar_contextos import EnrichedIndex, MontarContextosUseCase

    _RE_CODIGO = re.compile(r"^(\d+\.\d+)")

    raw = json.loads(ENRICHED_SNAPSHOT.read_text(encoding="utf-8"))
    tasks: list[ClickUpTaskEnriched] = []
    if isinstance(raw, dict) and "tasks" in raw:
        tasks = ClickUpEnrichedSnapshot.model_validate(raw).tasks
    elif isinstance(raw, dict):
        for tid, tdata in raw.items():
            if not isinstance(tdata, dict) or "base" not in tdata:
                continue
            tdata.setdefault("task_id", tid)
            try:
                tasks.append(ClickUpTaskEnriched.model_validate(tdata))
            except Exception:
                pass
    logger.info("%d tasks carregadas do enriched snapshot", len(tasks))

    payload = {"tasks": []}
    for t in tasks:
        b = t.base
        d = b.model_dump()
        d["id"] = t.task_id
        d["custom_fields"] = t.customfields or b.customfields or []
        payload["tasks"].append(d)
    relatorio = to_report_base_from_clickup(payload)
    logger.info(
        "Relatório canônico: %d metas, %d atividades",
        len(relatorio.metas),
        sum(len(m.atividades) for m in relatorio.metas),
    )

    index_dict: dict = {}
    for task in tasks:
        m = _RE_CODIGO.match((task.base.name or "").strip())
        if m:
            index_dict[m.group(1)] = task
    enriched_index = EnrichedIndex(task_por_codigo=index_dict)
    logger.info("%d atividades indexadas por código", len(index_dict))

    projeto_pdf = None
    if PDF_PROJETO.exists():
        try:
            projeto_pdf = extrair_projeto(ler_pdf_projeto(PDF_PROJETO))
            logger.info("PDF carregado: %d atividades extraídas", len(projeto_pdf.atividades))
        except Exception as e:
            logger.warning("Falha ao ler PDF: %s — datas virão nulas", e)
    else:
        logger.warning("PDF não encontrado em %s — datas virão nulas", PDF_PROJETO)

    uc = MontarContextosUseCase()
    resultado = uc.executar(relatorio, enriched_index, projeto_pdf=projeto_pdf)
    logger.info(resultado.resumo())

    ctx_by_codigo = {c.codigo: c for c in resultado.contextos}
    for meta in relatorio.metas:
        for atv in meta.atividades:
            codigo = atv.numero_atividade_original or atv.numero_atividade or atv.atividade_id
            ctx = ctx_by_codigo.get(codigo)
            if not ctx:
                continue
            if ctx.data_inicio:
                atv.datas.data_inicio = ctx.data_inicio.isoformat()
            if ctx.data_fim:
                atv.datas.data_fim = ctx.data_fim.isoformat()
            if ctx.progresso:
                atv.progresso = ctx.progresso

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    RELATORIO_PROG.write_text(relatorio.model_dump_json(indent=2), encoding="utf-8")
    logger.info("Relatório com progresso salvo em: %s", RELATORIO_PROG)


def etapa_4_gerar_textos(
    model: str,
    max_tentativas: int,
    atividades_filtro: list[str] | None,
) -> None:
    _sep("ETAPA 4 — Agentes IA: writer → validator → retry → merger")

    for path, nome in [
        (PDF_PROJETO,       "Termo PDF"),
        (RELATORIO_PROG,    "Relatório de progresso"),
        (ENRICHED_SNAPSHOT, "Enriched snapshot ClickUp"),
    ]:
        if not path.exists():
            logger.error("%s não encontrado: %s", nome, path)
            sys.exit(1)

    client = _build_llm_client(model)

    from app.application.use_cases.gerar_textos_atividades import executar

    t0 = time.time()
    relatorio_final = executar(
        termo_pdf_path=PDF_PROJETO,
        relatorio_progresso_path=RELATORIO_PROG,
        clickup_snapshot_path=ENRICHED_SNAPSHOT,
        output_path=RELATORIO_TEXTOS,
        llm_client=client,
        model=model,
        max_tentativas=max_tentativas,
        atividades_filtro=atividades_filtro,
    )
    elapsed = time.time() - t0

    total = sum(len(m.get("atividades", [])) for m in relatorio_final.get("metas", []))
    logger.info("")
    logger.info("Pipeline concluído em %.1fs", elapsed)
    logger.info("%d atividades no relatório final", total)
    logger.info("Resultado: %s", RELATORIO_TEXTOS)


# ── main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pipeline completo: ClickUp → enriquecimento → progresso → textos IA"
    )
    parser.add_argument(
        "--etapa-inicio",
        type=int,
        default=1,
        choices=[1, 2, 3, 4],
        help="Etapa a partir da qual iniciar (1=base, 2=enriched, 3=progresso, 4=textos)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=DEFAULT_MODEL,
        help=f"Modelo LLM para etapa 4 (padrão: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--tentativas",
        type=int,
        default=3,
        help="Máximo de tentativas por atividade (etapa 4)",
    )
    parser.add_argument(
        "--atividades",
        nargs="+",
        default=None,
        help="Filtro de atividades para etapa 4 (ex: 2.1 4.1 6.1 16.1)",
    )
    args = parser.parse_args()

    inicio = args.etapa_inicio

    if inicio <= 1:
        etapa_1_base_snapshot()
    if inicio <= 2:
        etapa_2_enriched_snapshot()
    if inicio <= 3:
        etapa_3_relatorio_progresso()
    if inicio <= 4:
        etapa_4_gerar_textos(
            model=args.model,
            max_tentativas=args.tentativas,
            atividades_filtro=args.atividades,
        )


if __name__ == "__main__":
    main()

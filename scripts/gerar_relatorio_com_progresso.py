"""
Gera relatorio_final_com_progresso.json

Lê o relatório canônico + enriched snapshot do ClickUp,
monta contextos com progresso calculado e exporta JSON final.

Rodar: python -m scripts.gerar_relatorio_com_progresso
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from app.domain.clickup.models import ClickUpEnrichedSnapshot, ClickUpTaskEnriched
from app.application.use_cases.montar_contextos import EnrichedIndex, MontarContextosUseCase
from app.domain.reporting.canonical_schemas import RelatorioCanonico

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── paths ─────────────────────────────────────────────────────────────────────

RELATORIO_PATH = Path("data/staged/relatorio_com_progresso_clickup_api.json")
SNAPSHOT_PATH  = Path("data/staged/clickup_enriched_snapshot.json")
OUTPUT_PATH    = Path("data/output/relatorio_final_com_progresso.json")


# ── helpers ───────────────────────────────────────────────────────────────────

def _carregar_relatorio(path: Path) -> RelatorioCanonico:
    logger.info("Carregando relatório: %s", path)
    return RelatorioCanonico.model_validate(json.loads(path.read_text(encoding="utf-8")))


def _carregar_index(path: Path) -> EnrichedIndex:
    """
    Monta EnrichedIndex indexado por código de atividade (ex: '1.1').

    O snapshot pode estar em dois formatos:
      1. {"metadata": ..., "tasks": [...]}  → ClickUpEnrichedSnapshot
      2. {"abc123": {...task...}, ...}       → dict flat por task_id

    Em ambos os casos, tentamos usar o campo 'name' da task como código,
    extraindo o padrão N.N do início do nome (ex: '1.2 - Título' → '1.2').
    """
    import re
    logger.info("Carregando enriched snapshot: %s", path)
    raw = json.loads(path.read_text(encoding="utf-8"))

    tasks: list[ClickUpTaskEnriched] = []

    if isinstance(raw, dict) and "tasks" in raw:
        snapshot = ClickUpEnrichedSnapshot.model_validate(raw)
        tasks = snapshot.tasks
    elif isinstance(raw, dict):
        # formato flat: chave = task_id, valor = objeto da task
        for tid, tdata in raw.items():
            if isinstance(tdata, dict):
                # garante que task_id está presente
                tdata.setdefault("task_id", tid)
                if "base" not in tdata and "id" not in tdata:
                    continue
                try:
                    tasks.append(ClickUpTaskEnriched.model_validate(tdata))
                except Exception:
                    pass
    elif isinstance(raw, list):
        for tdata in raw:
            try:
                tasks.append(ClickUpTaskEnriched.model_validate(tdata))
            except Exception:
                pass

    # indexa por código extraído do nome (padrão "N.N" no início)
    _RE_CODIGO = re.compile(r"^(\d+\.\d+)")
    index: dict[str, ClickUpTaskEnriched] = {}
    sem_codigo = 0

    for task in tasks:
        nome = task.base.name or ""
        m = _RE_CODIGO.match(nome.strip())
        if m:
            codigo = m.group(1)
            index[codigo] = task
        else:
            sem_codigo += 1

    logger.info(
        "EnrichedIndex: %d tasks indexadas por código, %d sem código extraível",
        len(index), sem_codigo,
    )
    return EnrichedIndex(task_por_codigo=index)


# ── pipeline ──────────────────────────────────────────────────────────────────

def main() -> None:
    relatorio = _carregar_relatorio(RELATORIO_PATH)
    index     = _carregar_index(SNAPSHOT_PATH)

    uc        = MontarContextosUseCase()
    resultado = uc.executar(relatorio, index, projeto_pdf=None)

    logger.info(resultado.resumo())

    # ── injeta progresso e datas calculadas de volta no relatório canônico ──
    ctx_by_codigo = {c.codigo: c for c in resultado.contextos}

    for meta in relatorio.metas:
        for atv in meta.atividades:
            codigo = (
                atv.numero_atividade_original
                or atv.numero_atividade
                or atv.atividade_id
            )
            ctx = ctx_by_codigo.get(codigo)
            if not ctx:
                continue

            # datas
            if ctx.data_inicio:
                atv.datas.data_inicio = ctx.data_inicio.isoformat()
            if ctx.data_fim:
                atv.datas.data_fim = ctx.data_fim.isoformat()

            # progresso
            if ctx.progresso:
                atv.progresso = ctx.progresso

    # ── exporta ──────────────────────────────────────────────────────────────
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        relatorio.model_dump_json(indent=2),
        encoding="utf-8",
    )

    logger.info("JSON final gerado em: %s", OUTPUT_PATH)

    # ── diagnóstico resumido ──────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print(resultado.resumo())
    print("=" * 60)

    print("\nPrimeiros 5 contextos:")
    for ctx in resultado.contextos[:5]:
        print(f"  [{ctx.codigo}] {ctx.titulo}")
        print(f"    origem_datas : {ctx.origem_datas}")
        print(f"    data_inicio  : {ctx.data_inicio}")
        print(f"    data_fim     : {ctx.data_fim}")
        p = ctx.progresso
        if p:
            print(f"    situacao     : {p.situacao_prazo}")
            print(f"    previsto     : {p.previsto_percentual}%")
            print(f"    realizado    : {p.realizado_percentual}%")
        print()

    if resultado.codigos_sem_dados:
        print(f"Sem dados ({len(resultado.codigos_sem_dados)}):")
        for c in resultado.codigos_sem_dados:
            print(f"  - {c}")

    print(f"\nJSON salvo em: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

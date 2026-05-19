"""
Gera relatorio_final_com_progresso.json

Fluxo correto:
  1. Lê o clickup_enriched_snapshot.json (fonte única de verdade)
  2. Constrói o RelatorioCanonico via mapper.py (extrai metas/atividades do nome das tasks)
  3. Monta EnrichedIndex indexado por código "N.N" (extraído do base.name)
  4. Roda MontarContextosUseCase → calcula progresso e preenche datas
  5. Injeta resultado de volta no relatório canônico
  6. Exporta relatorio_final_com_progresso.json

Rodar: python -m scripts.gerar_relatorio_com_progresso
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from app.domain.clickup.mapper import to_report_base_from_clickup
from app.domain.clickup.models import ClickUpEnrichedSnapshot, ClickUpTaskEnriched
from app.application.use_cases.montar_contextos import EnrichedIndex, MontarContextosUseCase

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── paths ─────────────────────────────────────────────────────────────────────

SNAPSHOT_PATH = Path("data/input/clickup_enriched_snapshot.json")
OUTPUT_PATH   = Path("data/output/relatorio_final_com_progresso.json")

_RE_CODIGO = re.compile(r"^(\d+\.\d+)")


# ── helpers ───────────────────────────────────────────────────────────────────

def _carregar_snapshot(path: Path) -> tuple[dict, list[ClickUpTaskEnriched]]:
    """
    Lê o snapshot e devolve (raw_dict, lista de ClickUpTaskEnriched).

    Suporta dois formatos:
      1. {"metadata": ..., "tasks": [...]}   → envelope ClickUpEnrichedSnapshot
      2. {"task_id": {...}, ...}              → dict flat por task_id (formato legado)
    """
    logger.info("Carregando snapshot: %s", path)
    raw: dict = json.loads(path.read_text(encoding="utf-8"))

    tasks: list[ClickUpTaskEnriched] = []

    if isinstance(raw, dict) and "tasks" in raw:
        snapshot = ClickUpEnrichedSnapshot.model_validate(raw)
        tasks = snapshot.tasks
        logger.info("Formato: envelope ClickUpEnrichedSnapshot — %d tasks", len(tasks))
    elif isinstance(raw, dict):
        # formato flat legado: chave = task_id
        for tid, tdata in raw.items():
            if not isinstance(tdata, dict):
                continue
            tdata.setdefault("task_id", tid)
            if "base" not in tdata:
                continue
            try:
                tasks.append(ClickUpTaskEnriched.model_validate(tdata))
            except Exception as exc:
                logger.debug("task %s ignorada: %s", tid, exc)
        logger.info("Formato: dict flat legado — %d tasks carregadas", len(tasks))
    else:
        logger.warning("Formato de snapshot não reconhecido.")

    return raw, tasks


def _montar_payload_para_mapper(tasks: list[ClickUpTaskEnriched]) -> dict:
    """
    O mapper.py espera {"tasks": [dict bruto]}.
    Reconstrói esse payload a partir das tasks enriquecidas usando os campos de base.
    """
    task_dicts = []
    for t in tasks:
        b = t.base
        d = b.model_dump()
        # garante que campos de lista/hierarquia estejam presentes
        d["id"]             = t.task_id
        d["name"]           = b.name
        d["parent"]         = b.parent
        d["toplevelparent"] = b.toplevelparent
        d["status"]         = b.status
        d["startdate"]      = b.startdate
        d["duedate"]        = b.duedate
        d["datedone"]       = b.datedone
        d["custom_fields"]  = t.customfields or b.customfields or []
        task_dicts.append(d)
    return {"tasks": task_dicts}


def _montar_index(tasks: list[ClickUpTaskEnriched]) -> EnrichedIndex:
    """
    Indexa tasks por código de atividade extraído do nome (padrão "N.N").
    Ex: "1.2 - Capacitação da equipe" → chave "1.2"
    """
    index: dict[str, ClickUpTaskEnriched] = {}
    sem_codigo = 0

    for task in tasks:
        nome = (task.base.name or "").strip()
        m = _RE_CODIGO.match(nome)
        if m:
            index[m.group(1)] = task
        else:
            sem_codigo += 1

    logger.info(
        "EnrichedIndex: %d atividades indexadas por código, %d tasks sem código (metas/outros)",
        len(index), sem_codigo,
    )
    return EnrichedIndex(task_por_codigo=index)


# ── pipeline ──────────────────────────────────────────────────────────────────

def main() -> None:
    # 1. carrega snapshot
    raw, tasks = _carregar_snapshot(SNAPSHOT_PATH)

    # 2. constrói relatório canônico via mapper (extrai metas e atividades)
    payload   = _montar_payload_para_mapper(tasks)
    relatorio = to_report_base_from_clickup(payload)
    logger.info(
        "Relatório canônico: %d metas, %d atividades totais",
        len(relatorio.metas),
        sum(len(m.atividades) for m in relatorio.metas),
    )

    # 3. monta índice enriquecido por código
    index = _montar_index(tasks)

    # 4. monta contextos + calcula progresso
    uc        = MontarContextosUseCase()
    resultado = uc.executar(relatorio, index, projeto_pdf=None)
    logger.info(resultado.resumo())

    # 5. injeta progresso e datas no relatório canônico
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

            if ctx.data_inicio:
                atv.datas.data_inicio = ctx.data_inicio.isoformat()
            if ctx.data_fim:
                atv.datas.data_fim = ctx.data_fim.isoformat()
            if ctx.progresso:
                atv.progresso = ctx.progresso

    # 6. exporta JSON final
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        relatorio.model_dump_json(indent=2),
        encoding="utf-8",
    )
    logger.info("JSON final gerado em: %s", OUTPUT_PATH)

    # ── diagnóstico no terminal ───────────────────────────────────────────────
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
        print(f"Sem dados suficientes ({len(resultado.codigos_sem_dados)}):")
        for c in resultado.codigos_sem_dados:
            print(f"  - {c}")

    print(f"\nJSON salvo em: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

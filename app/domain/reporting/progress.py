"""
Cálculo de progresso de atividades — Regras de Negócio v2.

REGRA GERAL DE realizado_percentual:
  1. Se status == "concluido"
       → sempre 100.0 (independente de datas ou checklists)

  2. Se há itens de ação (checklists) com total > 0
       → percentual = itens_concluidos / total_itens * 100
       (consolida TODOS os checklists da tarefa — Entregáveis + Indicador de Progresso)
       EXCEÇÃO: se o percentual chegar a 100% mas o status não for "concluido",
       capeia em 99% (dados inconsistentes no ClickUp — checklist marcado mas
       status não atualizado).

  3. Sem itens de ação + status == "pendente" ou "nao_iniciada"
       → 0.0 (nenhuma evidência de progresso)

  4. Sem itens de ação + status == "em_progresso" + dentro do prazo
       → percentual de tempo decorrido entre data_inicio e data_fim
         PISO EM 0%: se agora < data_inicio (atividade futura), retorna 0%.

  5. Sem itens de ação + status == "em_progresso" + atrasada (passou da data_fim)
       → percentual baseado em (agora - inicio) / (fim - inicio),
         capeado em 99.0 para não confundir com concluído

  Se datas forem inválidas (nulas, início == fim, início > fim):
       → retorna None para previsto_percentual (não é possível calcular)
       → realizado_percentual cai para a regra 3 (0.0 sem evidência)

DATAS:
  As datas planejadas podem vir de duas fontes, na ordem de prioridade:
    1. data_inicio_override / data_fim_override  → vindas do PDF (via ContextoAtividade)
    2. task.base.startdate / task.base.duedate   → vindas do ClickUp

  Isso é necessário porque muitas tasks no ClickUp não têm datas preenchidas,
  sendo as datas extraídas do PDF do projeto a fonte canônica nesses casos.

AGREGAÇÃO DE META-PAI:
  calcular_progresso_meta() computa a média simples do realizado_percentual
  e do previsto_percentual de todas as atividades-filhas com valor definido.
  Deve ser chamada no script de ingestão para popular progresso_calculado_meta.

Não acessa o ClickUp nem faz I/O — pura lógica de domínio.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Optional

from app.domain.clickup.models import ClickUpTaskEnriched
from app.domain.reporting.canonical_schemas import ProgressoAtividadeCanonico

logger = logging.getLogger(__name__)


# ── helpers internos ──────────────────────────────────────────────────────────

def _ms_to_dt(ms: Optional[int]) -> Optional[datetime]:
    if ms is None:
        return None
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


def _date_to_ms(d: Optional[date]) -> Optional[int]:
    """date → timestamp em ms (meio-dia UTC para evitar off-by-one de fuso)."""
    if d is None:
        return None
    return int(datetime(d.year, d.month, d.day, 12, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)


def _ms_to_mesano(ms: Optional[int]) -> Optional[str]:
    """Timestamp ms → string 'MM/AAAA'. Ex: 1777446000000 → '04/2026'."""
    dt = _ms_to_dt(ms)
    if dt is None:
        return None
    return dt.strftime("%m/%Y")


def _date_to_mesano(d: Optional[date]) -> Optional[str]:
    if d is None:
        return None
    return d.strftime("%m/%Y")


def _dias_entre(inicio_ms: Optional[int], fim_ms: Optional[int]) -> Optional[int]:
    if inicio_ms is None or fim_ms is None:
        return None
    delta = _ms_to_dt(fim_ms) - _ms_to_dt(inicio_ms)  # type: ignore[operator]
    return max(0, delta.days)


def _percentual_cronograma(
    inicio_ms: Optional[int],
    fim_ms: Optional[int],
    agora: Optional[datetime] = None,
) -> Optional[float]:
    """
    Percentual de tempo decorrido dentro do intervalo planejado.

    Retorna None se datas forem inválidas (nulas ou sem duração real).
    Garante piso em 0%: quando agora < inicio (atividade futura ou data
    malformada no ClickUp), retorna 0.0 em vez de valor negativo.
    Quando atrasada (agora > fim), pode ultrapassar 100% — o chamador
    decide se capeia ou não dependendo do contexto.
    """
    if inicio_ms is None or fim_ms is None:
        return None
    if inicio_ms >= fim_ms:
        return None
    agora = agora or datetime.now(tz=timezone.utc)
    agora_ms = agora.timestamp() * 1000
    ratio = (agora_ms - inicio_ms) / (fim_ms - inicio_ms)
    # Piso em 0%: evita valores negativos quando agora < inicio_ms
    return round(max(0.0, ratio) * 100, 2)


def _percentual_checklists(task: ClickUpTaskEnriched) -> Optional[float]:
    """
    Calcula o percentual de conclusão com base nos itens de ação (checklists).

    Consolida TODOS os checklists da tarefa (Entregáveis, Indicador de Progresso etc.).
    Usa checklists_summary quando disponível (mais eficiente); faz fallback para
    contagem direta em checklists[].items[] quando necessário.

    Retorna None se não houver itens de ação definidos.
    """
    summaries = task.checklists_summary or []
    if summaries:
        total = sum(s.get("total", 0) for s in summaries)
        concluidos = sum(s.get("concluidos", 0) for s in summaries)
        if total > 0:
            return round((concluidos / total) * 100, 2)

    # Fallback: conta diretamente nos itens de cada checklist
    checklists = task.checklists or []
    if not checklists:
        return None

    total = 0
    concluidos = 0
    for checklist in checklists:
        items = checklist.get("items", []) or []
        for item in items:
            total += 1
            if item.get("resolved") is True:
                concluidos += 1

    if total == 0:
        return None

    return round((concluidos / total) * 100, 2)


def _status_normalizado(status: str) -> str:
    s = (status or "").lower().strip()
    if s in {"concluído", "concluido", "done", "closed", "complete", "completed"}:
        return "concluido"
    if s in {"em progresso", "in progress", "in_progress", "doing"}:
        return "em_progresso"
    if s in {"pendente", "pending", "open", "to do", "todo", "not started"}:
        return "pendente"
    return s


def _situacao_prazo(
    concluido: bool,
    em_progresso: bool,
    atrasada: bool,
    fim_ms: Optional[int],
) -> str:
    if concluido:
        return "concluida_em_atraso" if atrasada else "concluida_no_prazo"
    if em_progresso:
        return "em_progresso_atrasada" if atrasada else "em_progresso_no_prazo"
    if fim_ms is None:
        return "nao_iniciada_sem_prazo"
    return "nao_iniciada_atrasada" if atrasada else "nao_iniciada_no_prazo"


# ── agregação de meta-pai ─────────────────────────────────────────────────────

def calcular_progresso_meta(atividades: list[dict]) -> dict:
    """
    Agrega o progresso das atividades-filhas para compor o indicador da meta-pai.

    Calcula a média simples de realizado_percentual e previsto_percentual
    de todas as atividades que possuem esses campos definidos (não-None).

    Tolerante às três chaves possíveis para o bloco de progresso:
      - 'progresso_calculado'  → gerado pelo script legado dos notebooks
      - 'progresso'            → estrutura canônica nova
      - 'progressoCalculado'   → variante camelCase

    Args:
        atividades: lista de dicts de atividade do relatório (qualquer estrutura).

    Returns:
        Dict com 'realizado_percentual' e 'previsto_percentual' (float ou None).

    Exemplo:
        >>> metas = relatorio["relatorio"]["secoes_fixas"][SECAO_KEY]["itens_meta_atividade"]
        >>> for meta in metas:
        ...     meta["progresso_calculado_meta"] = calcular_progresso_meta(meta["atividades"])
    """
    realizados: list[float] = []
    previstos: list[float] = []

    for atv in atividades:
        prog = (
            atv.get("progresso_calculado")
            or atv.get("progresso")
            or atv.get("progressoCalculado")
            or {}
        )
        r = prog.get("realizado_percentual")
        p = prog.get("previsto_percentual")

        if r is not None:
            try:
                realizados.append(float(r))
            except (TypeError, ValueError):
                pass
        if p is not None:
            try:
                previstos.append(float(p))
            except (TypeError, ValueError):
                pass

    realizado_media = round(sum(realizados) / len(realizados), 1) if realizados else None
    previsto_media  = round(sum(previstos)  / len(previstos),  1) if previstos  else None

    logger.debug(
        "calcular_progresso_meta: %d atividades → realizado=%.1f%% previsto=%.1f%%",
        len(atividades),
        realizado_media or 0.0,
        previsto_media  or 0.0,
    )

    return {
        "realizado_percentual": realizado_media,
        "previsto_percentual":  previsto_media,
    }


# ── função pública ────────────────────────────────────────────────────────────

def calcular_progresso(
    task: ClickUpTaskEnriched,
    data_inicio_override: Optional[date] = None,
    data_fim_override: Optional[date] = None,
) -> ProgressoAtividadeCanonico:
    """
    Calcula ProgressoAtividadeCanonico a partir de uma ClickUpTaskEnriched.

    Fontes de data (em ordem de prioridade):
        data_inicio_override   →  vinda do PDF via ContextoAtividade (prioridade 1)
        data_fim_override      →  vinda do PDF via ContextoAtividade (prioridade 1)
        task.base.startdate    →  start_date do ClickUp              (prioridade 2)
        task.base.duedate      →  due_date do ClickUp                (prioridade 2)
        task.base.datedone     →  data_realizada_fim (ClickUp)
        task.base.dateclosed   →  fallback de data_realizada_fim

    Ver docstring do módulo para as regras completas de realizado_percentual.
    """
    agora = datetime.now(tz=timezone.utc)
    agora_ms = agora.timestamp() * 1000

    # Resolve datas: override do PDF tem prioridade sobre ClickUp
    ini_ms = _date_to_ms(data_inicio_override) if data_inicio_override else task.data_planejada_inicio_ms
    fim_ms = _date_to_ms(data_fim_override)    if data_fim_override    else task.data_planejada_fim_ms

    # Origem das datas para rastreabilidade (usado só em log)
    origem_ini = "pdf" if data_inicio_override else ("clickup" if task.data_planejada_inicio_ms else "ausente")
    origem_fim = "pdf" if data_fim_override     else ("clickup" if task.data_planejada_fim_ms    else "ausente")

    feito_ms = task.data_realizada_fim_ms
    status   = _status_normalizado(task.base.status or "")

    concluido    = status == "concluido"
    em_progresso = status == "em_progresso"

    logger.debug(
        "calcular_progresso task=%s status=%s ini_ms=%s(%s) fim_ms=%s(%s)",
        task.task_id, status, ini_ms, origem_ini, fim_ms, origem_fim,
    )

    # ── flag de atraso ────────────────────────────────────────────────────────
    if concluido:
        atrasada = bool(feito_ms and fim_ms and feito_ms > fim_ms)
    else:
        atrasada = fim_ms is not None and agora_ms > fim_ms

    # ── realizado_percentual — aplicar regras na ordem de prioridade ──────────

    # Regra 1: concluído → sempre 100%
    if concluido:
        realizado_pct = 100.0

    else:
        # Regra 2: tem itens de ação → usar checklists
        pct_checklist = _percentual_checklists(task)
        if pct_checklist is not None:
            if pct_checklist >= 100.0:
                # Checklist totalmente marcado mas status não é "concluido"
                # → dados inconsistentes no ClickUp; capeia em 99% para não
                #   confundir com conclusão real
                logger.warning(
                    "task %s: checklist 100%% mas status='%s' — capeando em 99%%",
                    task.task_id, status,
                )
                realizado_pct = 99.0
            else:
                realizado_pct = pct_checklist

        # Regra 3: sem itens de ação + não em progresso → 0%
        elif not em_progresso:
            realizado_pct = 0.0

        else:
            # Regras 4 e 5: em progresso sem checklists → calcular por tempo
            # _percentual_cronograma já garante piso em 0% internamente
            pct_tempo = _percentual_cronograma(ini_ms, fim_ms, agora)

            if pct_tempo is None:
                realizado_pct = 0.0
            elif atrasada:
                realizado_pct = min(pct_tempo, 99.0)
            else:
                realizado_pct = min(pct_tempo, 100.0)

    # ── previsto_percentual ───────────────────────────────────────────────────
    # _percentual_cronograma já garante piso em 0% internamente
    previsto_pct = _percentual_cronograma(ini_ms, fim_ms, agora)
    if previsto_pct is not None:
        previsto_pct = min(previsto_pct, 100.0)

    # ── campos de data para o schema canônico ─────────────────────────────────
    # Prefere formatar a partir do date override (mais preciso); fallback para ms
    mes_ano_ini_prev = _date_to_mesano(data_inicio_override) or _ms_to_mesano(task.data_planejada_inicio_ms)
    mes_ano_fim_prev = _date_to_mesano(data_fim_override)    or _ms_to_mesano(task.data_planejada_fim_ms)

    return ProgressoAtividadeCanonico(
        atrasada=atrasada,
        situacao_prazo=_situacao_prazo(concluido, em_progresso, atrasada, fim_ms),
        duracao_prevista_dias=_dias_entre(ini_ms, fim_ms),
        duracao_efetiva_dias=_dias_entre(ini_ms, feito_ms) if feito_ms else None,
        mes_ano_inicio_previsto=mes_ano_ini_prev,
        mes_ano_fim_previsto=mes_ano_fim_prev,
        mes_ano_inicio_real=mes_ano_ini_prev if (concluido or em_progresso) else None,
        mes_ano_fim_real=_ms_to_mesano(feito_ms),
        previsto_percentual=previsto_pct,
        realizado_percentual=realizado_pct,
    )

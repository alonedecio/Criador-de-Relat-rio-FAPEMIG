"""
Cálculo de progresso de atividades — Regras de Negócio v2.

REGRA GERAL DE realizado_percentual:
  1. Se status == "concluido"
       → sempre 100.0 (independente de datas ou checklists)

  2. Se há itens de ação (checklists) com total > 0
       → percentual = itens_concluidos / total_itens * 100
       (consolida TODOS os checklists da tarefa — Entregáveis + Indicador de Progresso)

  3. Sem itens de ação + status == "pendente" ou "nao_iniciada"
       → 0.0 (nenhuma evidência de progresso)

  4. Sem itens de ação + status == "em_progresso" + dentro do prazo
       → percentual de tempo decorrido entre data_inicio e data_fim

  5. Sem itens de ação + status == "em_progresso" + atrasada (passou da data_fim)
       → percentual baseado em (agora - inicio) / (fim - inicio),
         capeado em 99.0 para não confundir com concluído

  Se datas forem inválidas (nulas, início == fim, início > fim):
       → retorna None para previsto_percentual (não é possível calcular)
       → realizado_percentual cai para a regra 3 (0.0 sem evidência)

Não acessa o ClickUp nem faz I/O — pura lógica de domínio.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from app.domain.clickup.models import ClickUpTaskEnriched
from app.domain.reporting.canonical_schemas import ProgressoAtividadeCanonico


# ── helpers internos ──────────────────────────────────────────────────────────

def _ms_to_dt(ms: Optional[int]) -> Optional[datetime]:
    if ms is None:
        return None
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


def _ms_to_mesano(ms: Optional[int]) -> Optional[str]:
    """Timestamp ms → string 'MM/AAAA'. Ex: 1777446000000 → '04/2026'."""
    dt = _ms_to_dt(ms)
    if dt is None:
        return None
    return dt.strftime("%m/%Y")


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
    Quando atrasada (agora > fim), pode ultrapassar 100% — o chamador
    decide se capeia ou não dependendo do contexto.
    """
    if inicio_ms is None or fim_ms is None:
        return None
    if inicio_ms >= fim_ms:
        # Datas inválidas ou sem duração — não é possível calcular
        return None
    agora = agora or datetime.now(tz=timezone.utc)
    agora_ms = agora.timestamp() * 1000
    ratio = (agora_ms - inicio_ms) / (fim_ms - inicio_ms)
    return round(ratio * 100, 2)


def _percentual_checklists(task: ClickUpTaskEnriched) -> Optional[float]:
    """
    Calcula o percentual de conclusão com base nos itens de ação (checklists).

    Consolida TODOS os checklists da tarefa (Entregáveis, Indicador de Progresso etc.).
    Usa checklistssummary quando disponível (mais eficiente); faz fallback para
    contagem direta em checklists[].items[] quando necessário.

    Retorna None se não houver itens de ação definidos.
    """
    # Tenta usar checklistssummary (campo pré-calculado no snapshot enriquecido)
    summaries = task.checklists_summary or []
    if summaries:
        total = sum(s.get("total", 0) for s in summaries)
        concluidos = sum(s.get("concluidos", 0) for s in summaries)
        if total > 0:
            return round((concluidos / total) * 100, 2)

    # Fallback: conta diretamente nos itens de cada checklist
    checklists = getattr(task, "checklists", None) or []
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


# ── função pública ────────────────────────────────────────────────────────────

def calcular_progresso(task: ClickUpTaskEnriched) -> ProgressoAtividadeCanonico:
    """
    Calcula ProgressoAtividadeCanonico a partir de uma ClickUpTaskEnriched.

    Fontes de data:
        data_planejada_inicio  →  task.base.startdate  (start_date ClickUp)
        data_planejada_fim     →  task.base.duedate    (due_date   ClickUp)
        data_realizada_fim     →  task.base.datedone   (date_done  ClickUp)
                                  ou task.base.dateclosed como fallback

    Ver docstring do módulo para as regras completas de realizado_percentual.
    """
    agora = datetime.now(tz=timezone.utc)
    agora_ms = agora.timestamp() * 1000

    ini_ms = task.data_planejada_inicio_ms
    fim_ms = task.data_planejada_fim_ms
    feito_ms = task.data_realizada_fim_ms
    status = _status_normalizado(task.base.status or "")

    concluido = status == "concluido"
    em_progresso = status == "em_progresso"

    # ── flag de atraso ────────────────────────────────────────────────────────
    if concluido:
        # Atrasada se foi concluída depois da data fim planejada
        atrasada = bool(feito_ms and fim_ms and feito_ms > fim_ms)
    else:
        # Atrasada se a data fim já passou e ainda não foi concluída
        atrasada = fim_ms is not None and agora_ms > fim_ms

    # ── realizado_percentual — aplicar regras na ordem de prioridade ──────────

    # Regra 1: concluído → sempre 100%
    if concluido:
        realizado_pct = 100.0

    else:
        # Regra 2: tem itens de ação → usar checklists
        pct_checklist = _percentual_checklists(task)
        if pct_checklist is not None:
            realizado_pct = pct_checklist

        # Regra 3: sem itens de ação + não iniciada → 0%
        elif not em_progresso:
            realizado_pct = 0.0

        else:
            # Regras 4 e 5: em progresso sem checklists → calcular por tempo
            pct_tempo = _percentual_cronograma(ini_ms, fim_ms, agora)

            if pct_tempo is None:
                # Datas inválidas → sem evidência de progresso
                realizado_pct = 0.0
            elif atrasada:
                # Regra 5: atrasada → permite ultrapassar 100%, mas capeia em 99%
                # para não confundir com concluído (que é sempre 100% explícito)
                realizado_pct = min(pct_tempo, 99.0)
            else:
                # Regra 4: dentro do prazo → capeado normalmente em 100%
                realizado_pct = min(pct_tempo, 100.0)

    # ── previsto_percentual — quanto do prazo planejado já deveria ter passado ─
    previsto_pct = _percentual_cronograma(ini_ms, fim_ms, agora)
    if previsto_pct is not None:
        previsto_pct = min(previsto_pct, 100.0)  # previsto nunca passa de 100%

    return ProgressoAtividadeCanonico(
        atrasada=atrasada,
        situacao_prazo=_situacao_prazo(concluido, em_progresso, atrasada, fim_ms),
        duracao_prevista_dias=_dias_entre(ini_ms, fim_ms),
        duracao_efetiva_dias=_dias_entre(ini_ms, feito_ms) if feito_ms else None,
        mes_ano_inicio_previsto=_ms_to_mesano(ini_ms),
        mes_ano_fim_previsto=_ms_to_mesano(fim_ms),
        mes_ano_inicio_real=_ms_to_mesano(ini_ms) if (concluido or em_progresso) else None,
        mes_ano_fim_real=_ms_to_mesano(feito_ms),
        previsto_percentual=previsto_pct,
        realizado_percentual=realizado_pct,
    )
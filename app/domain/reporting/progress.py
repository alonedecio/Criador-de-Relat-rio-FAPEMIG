"""
Cálculo de progresso de atividades.

Recebe uma ClickUpTaskEnriched já carregada e devolve
ProgressoAtividadeCanonico pronto para o relatório.
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
    """Timestamp ms → string 'MMAAAA'. Ex: 1777446000000 → '042026'."""
    dt = _ms_to_dt(ms)
    if dt is None:
        return None
    return dt.strftime("%m%Y")


def _dias_entre(inicio_ms: Optional[int], fim_ms: Optional[int]) -> Optional[int]:
    if inicio_ms is None or fim_ms is None:
        return None
    delta = _ms_to_dt(fim_ms) - _ms_to_dt(inicio_ms)   # type: ignore[operator]
    return max(0, delta.days)


def _percentual_cronograma(
    inicio_ms: Optional[int],
    fim_ms:    Optional[int],
    agora:     Optional[datetime] = None,
) -> Optional[float]:
    """Percentual de tempo decorrido dentro do prazo planejado."""
    if inicio_ms is None or fim_ms is None:
        return None
    if inicio_ms >= fim_ms:
        return 100.0
    agora = agora or datetime.now(tz=timezone.utc)
    agora_ms = agora.timestamp() * 1000
    ratio = (agora_ms - inicio_ms) / (fim_ms - inicio_ms)
    return round(min(max(ratio * 100, 0.0), 100.0), 2)


def _status_normalizado(status: str) -> str:
    s = status.lower().strip()
    if s in {"concluído", "concluido", "done", "closed", "complete", "completed"}:
        return "concluido"
    if s in {"em progresso", "in progress", "in_progress", "doing"}:
        return "em_progresso"
    if s in {"pendente", "pending", "open", "to do", "todo", "not started"}:
        return "pendente"
    return s


def _situacao_prazo(
    concluido:    bool,
    em_progresso: bool,
    atrasada:     bool,
    fim_ms:       Optional[int],
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

    Fontes de data (reutilizando campos já existentes no snapshot):
        data_planejada_inicio  →  task.base.startdate   (start_date ClickUp)
        data_planejada_fim     →  task.base.duedate     (due_date   ClickUp)
        data_realizada_fim     →  task.base.datedone    (date_done  ClickUp)
                                  ou task.base.dateclosed como fallback
    """
    agora    = datetime.now(tz=timezone.utc)
    agora_ms = agora.timestamp() * 1000

    ini_ms   = task.data_planejada_inicio_ms
    fim_ms   = task.data_planejada_fim_ms
    feito_ms = task.data_realizada_fim_ms
    status   = _status_normalizado(task.base.status)

    concluido    = status == "concluido"
    em_progresso = status == "em_progresso"

    # percentual realizado
    if concluido:
        realizado_pct = 100.0
    elif em_progresso and ini_ms and fim_ms:
        realizado_pct = _percentual_cronograma(ini_ms, fim_ms, agora)
    else:
        realizado_pct = 0.0

    # percentual previsto (quanto do prazo já deveria ter passado)
    previsto_pct = _percentual_cronograma(ini_ms, fim_ms, agora)

    # flag de atraso
    if concluido:
        atrasada = bool(feito_ms and fim_ms and feito_ms > fim_ms)
    else:
        atrasada = fim_ms is not None and agora_ms > fim_ms

    return ProgressoAtividadeCanonico(
    atrasada=atrasada,
    situacao_prazo=_situacao_prazo(concluido, em_progresso, atrasada, fim_ms),
    duracao_prevista_dias=_dias_entre(ini_ms, fim_ms),
    duracao_efetiva_dias=_dias_entre(ini_ms, feito_ms) if feito_ms else None,
    mes_ano_inicio_previsto=_ms_to_mesano(ini_ms),
    mes_ano_fim_previsto=_ms_to_mesano(fim_ms),
    mes_ano_inicio_real=_ms_to_mesano(ini_ms) if (concluido or em_progresso) else None,
    mes_ano_fim_real=_ms_to_mesano(feito_ms),
    previsto_percentual=_percentual_cronograma(ini_ms, fim_ms, agora),
    realizado_percentual=realizado_pct,
)
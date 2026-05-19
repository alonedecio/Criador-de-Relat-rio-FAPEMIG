from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from app.domain.reporting.canonical_schemas import RelatorioCanonico


STATUS_CONCLUIDOS = {
    "concluida",
    "concluído",
    "concluido",
    "concluída",
    "closed",
    "complete",
    "done",
    "finalizada",
    "finalizado",
}

STATUS_EM_PROGRESSO = {
    "em progresso",
    "in progress",
    "progress",
    "working",
    "em andamento",
}

STATUS_PENDENTES = {
    "pendente",
    "open",
    "to do",
    "todo",
    "não iniciada",
    "nao iniciada",
}


def _to_dt(value: object) -> Optional[datetime]:
    if value in (None, ""):
        return None

    try:
        s = str(value).strip()

        if s.isdigit():
            if len(s) == 13:
                return datetime.fromtimestamp(int(s) / 1000, tz=timezone.utc)
            return datetime.fromtimestamp(int(s), tz=timezone.utc)

        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def _month_year(dt: Optional[datetime]) -> Optional[str]:
    if not dt:
        return None
    return dt.strftime("%m/%Y")


def _days_between(start: Optional[datetime], end: Optional[datetime]) -> Optional[int]:
    if not start or not end:
        return None
    return (end.date() - start.date()).days


def _normalize_status(status: Optional[str]) -> str:
    if not status:
        return ""
    return str(status).strip().lower()


def _calc_previsto_percentual(
    dt_inicio: Optional[datetime],
    dt_fim: Optional[datetime],
    hoje: datetime,
) -> Optional[float]:
    if not dt_inicio or not dt_fim:
        return None

    if dt_fim <= dt_inicio:
        return 100.0 if hoje >= dt_fim else 0.0

    if hoje <= dt_inicio:
        return 0.0

    if hoje >= dt_fim:
        return 100.0

    total = (dt_fim - dt_inicio).total_seconds()
    decorrido = (hoje - dt_inicio).total_seconds()
    return round((decorrido / total) * 100, 2)


def _calc_realizado_percentual(
    status_norm: str,
    dt_inicio: Optional[datetime],
    dt_fim: Optional[datetime],
    dt_fim_realizado: Optional[datetime],
    hoje: datetime,
) -> Optional[float]:
    if dt_fim_realizado:
        return 100.0

    if status_norm in STATUS_PENDENTES:
        return 0.0

    if status_norm in STATUS_EM_PROGRESSO:
        if dt_inicio and dt_fim:
            return _calc_previsto_percentual(dt_inicio, dt_fim, hoje)
        return None

    if status_norm in STATUS_CONCLUIDOS:
        return 100.0

    return None


def _calc_situacao_prazo(
    status_norm: str,
    dt_fim: Optional[datetime],
    dt_fim_realizado: Optional[datetime],
    hoje: datetime,
) -> str:
    if dt_fim_realizado:
        if dt_fim and dt_fim_realizado > dt_fim:
            return "concluida_em_atraso"
        return "concluida_no_prazo"

    atrasada = bool(dt_fim and hoje > dt_fim)

    if status_norm in STATUS_EM_PROGRESSO:
        return "em_progresso_atrasada" if atrasada else "em_progresso_no_prazo"

    if status_norm in STATUS_PENDENTES or not status_norm:
        return "nao_iniciada_atrasada" if atrasada else "nao_iniciada_no_prazo"

    return "atrasada" if atrasada else "no_prazo"


def enrich_report_progress(
    report: RelatorioCanonico,
    reference_datetime: Optional[datetime] = None,
) -> RelatorioCanonico:
    out = report.model_copy(deep=True)
    hoje = reference_datetime or datetime.now(timezone.utc)

    for meta in out.metas:
        if meta.progresso is None:
            continue

        previstos_meta: list[float] = []
        realizados_meta: list[float] = []

        for atividade in meta.atividades:
            dt_inicio = _to_dt(atividade.datas.data_inicio)
            dt_fim = _to_dt(atividade.datas.data_fim)
            dt_fim_realizado = _to_dt(atividade.datas.data_fim_realizado)
            status_norm = _normalize_status(atividade.status_clickup)

            dur_prev = _days_between(dt_inicio, dt_fim)
            dur_efet = _days_between(dt_inicio, dt_fim_realizado)

            previsto_pct = _calc_previsto_percentual(dt_inicio, dt_fim, hoje)
            realizado_pct = _calc_realizado_percentual(
                status_norm=status_norm,
                dt_inicio=dt_inicio,
                dt_fim=dt_fim,
                dt_fim_realizado=dt_fim_realizado,
                hoje=hoje,
            )
            situacao_prazo = _calc_situacao_prazo(
                status_norm=status_norm,
                dt_fim=dt_fim,
                dt_fim_realizado=dt_fim_realizado,
                hoje=hoje,
            )

            atividade.progresso.atrasada = situacao_prazo in {
                "concluida_em_atraso",
                "em_progresso_atrasada",
                "nao_iniciada_atrasada",
                "atrasada",
            }
            atividade.progresso.situacao_prazo = situacao_prazo
            atividade.progresso.duracao_prevista_dias = dur_prev
            atividade.progresso.duracao_efetiva_dias = dur_efet
            atividade.progresso.mes_ano_inicio_previsto = _month_year(dt_inicio)
            atividade.progresso.mes_ano_fim_previsto = _month_year(dt_fim)
            atividade.progresso.mes_ano_inicio_real = _month_year(dt_inicio) if dt_fim_realizado else None
            atividade.progresso.mes_ano_fim_real = _month_year(dt_fim_realizado)
            atividade.progresso.previsto_percentual = previsto_pct
            atividade.progresso.realizado_percentual = realizado_pct

            if previsto_pct is not None:
                previstos_meta.append(previsto_pct)
            if realizado_pct is not None:
                realizados_meta.append(realizado_pct)

        meta.progresso.previsto_percentual_medio = (
            round(sum(previstos_meta) / len(previstos_meta), 2) if previstos_meta else None
        )
        meta.progresso.realizado_percentual_medio = (
            round(sum(realizados_meta) / len(realizados_meta), 2) if realizados_meta else None
        )

    return out
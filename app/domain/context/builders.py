from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from app.domain.clickup.models import ClickUpTaskEnriched
from app.domain.projects.pdf_extractor import AtividadePDF
from app.domain.reporting.canonical_schemas import ProgressoAtividadeCanonico


@dataclass
class FonteDado:
    campo:  str
    origem: str
    valor:  str


@dataclass
class ContextoAtividade:
    codigo:        str
    meta_codigo:   str
    titulo:        str
    data_inicio:   Optional[date]
    data_fim:      Optional[date]
    origem_datas:  str
    progresso:     Optional[ProgressoAtividadeCanonico]
    descricao:     str
    comentarios:   list[str]      = field(default_factory=list)
    checklists:    list[dict]     = field(default_factory=list)
    responsaveis:  list[str]      = field(default_factory=list)
    anexos:        list           = field(default_factory=list)
    customfields:  list[dict]     = field(default_factory=list)  # itens de ação e campos extras
    status:        str            = "pendente"
    fontes:        list[FonteDado] = field(default_factory=list)
    task_id:       Optional[str]  = None

    def tem_dados_suficientes(self) -> bool:
        return bool(self.titulo and self.data_inicio and self.data_fim)


def _ms_to_date(ms: Optional[int]) -> Optional[date]:
    if ms is None:
        return None
    from datetime import datetime, timezone
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).date()


def _extrair_responsaveis(task: ClickUpTaskEnriched) -> list[str]:
    nomes = []
    for a in task.assignees:
        nome = a.get("username") or a.get("email") or a.get("id", "")
        if nome:
            nomes.append(str(nome))
    return nomes


def _extrair_comentarios(task: ClickUpTaskEnriched) -> list[str]:
    textos = []
    for c in task.comments:
        texto = c.get("comment_text") or c.get("text") or ""
        if texto.strip():
            textos.append(texto.strip())
    return textos


def _extrair_anexos(task: ClickUpTaskEnriched) -> list:
    """
    Extrai anexos da task do ClickUp.
    A API retorna uma lista de dicts com campos como 'title', 'filename', 'url'.
    Preservamos o dict completo para o prompt usar o titulo como evidencia inferivel.
    """
    raw = getattr(task, "attachments", None) or []
    resultado = []
    for a in raw:
        if isinstance(a, dict):
            resultado.append(a)
        elif isinstance(a, str) and a.strip():
            resultado.append({"title": a})
    return resultado


def _extrair_customfields(task: ClickUpTaskEnriched) -> list[dict]:
    """
    Extrai customfields da task enriquecida.
    Prioriza task.customfields (enriquecido) sobre task.base.customfields.
    Filtra campos sem valor para não poluir o contexto.
    """
    raw = task.customfields or task.base.customfields or []
    resultado = []
    for cf in raw:
        if not isinstance(cf, dict):
            continue
        valor = (
            cf.get("value")
            or cf.get("value_richtext")
            or ""
        )
        if str(valor).strip():
            resultado.append(cf)
    return resultado


def _fonte(campo: str, origem: str, valor: str) -> FonteDado:
    return FonteDado(campo=campo, origem=origem, valor=valor)


def montar_contexto(
    codigo:    str,
    titulo:    str,
    task:      Optional[ClickUpTaskEnriched],
    pdf_atv:   Optional[AtividadePDF],
    progresso: Optional[ProgressoAtividadeCanonico] = None,
) -> ContextoAtividade:
    fontes: list[FonteDado] = []
    meta_codigo = codigo.split(".")[0] if "." in codigo else codigo

    data_inicio: Optional[date] = None
    data_fim:    Optional[date] = None
    origem_datas = "ausente"

    if task:
        data_inicio = _ms_to_date(task.data_planejada_inicio_ms)
        data_fim    = _ms_to_date(task.data_planejada_fim_ms)
        if data_inicio or data_fim:
            origem_datas = "clickup"
            fontes.append(_fonte("data_inicio", "clickup", str(data_inicio)))
            fontes.append(_fonte("data_fim",    "clickup", str(data_fim)))

    if pdf_atv and not (data_inicio and data_fim):
        if pdf_atv.data_inicio_abs:
            data_inicio  = pdf_atv.data_inicio_abs
            origem_datas = "pdf"
            fontes.append(_fonte("data_inicio", "pdf", str(data_inicio)))
        if pdf_atv.data_fim_abs:
            data_fim     = pdf_atv.data_fim_abs
            origem_datas = "pdf"
            fontes.append(_fonte("data_fim", "pdf", str(data_fim)))

    if not (data_inicio or data_fim):
        fontes.append(_fonte("data_inicio", "ausente", ""))
        fontes.append(_fonte("data_fim",    "ausente", ""))

    descricao     = ""
    comentarios:  list[str]  = []
    checklists:   list[dict] = []
    responsaveis: list[str]  = []
    anexos:       list       = []
    customfields: list[dict] = []
    status  = "pendente"
    task_id = None

    if task:
        descricao    = (task.description or task.textcontent or "").strip()
        comentarios  = _extrair_comentarios(task)
        checklists   = task.checklists or []
        responsaveis = _extrair_responsaveis(task)
        anexos       = _extrair_anexos(task)
        customfields = _extrair_customfields(task)
        status       = task.base.status
        task_id      = task.task_id
        fontes.append(_fonte("descricao",    "clickup", descricao[:80]))
        fontes.append(_fonte("status",       "clickup", status))
        fontes.append(_fonte("responsaveis", "clickup", ", ".join(responsaveis)))
        if anexos:
            fontes.append(_fonte("anexos", "clickup", f"{len(anexos)} anexo(s)"))
        if customfields:
            fontes.append(_fonte("customfields", "clickup", f"{len(customfields)} campo(s) com valor"))

    return ContextoAtividade(
        codigo=codigo,
        meta_codigo=meta_codigo,
        titulo=titulo,
        data_inicio=data_inicio,
        data_fim=data_fim,
        origem_datas=origem_datas,
        progresso=progresso,
        descricao=descricao,
        comentarios=comentarios,
        checklists=checklists,
        responsaveis=responsaveis,
        anexos=anexos,
        customfields=customfields,
        status=status,
        fontes=fontes,
        task_id=task_id,
    )

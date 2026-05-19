from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.config import TEMPLATES_DIR
from app.domain.reporting.schemas import RelatorioProjeto


class HTMLReportRenderer:
    def __init__(self) -> None:
        self.env = Environment(
            loader=FileSystemLoader(TEMPLATES_DIR),
            autoescape=select_autoescape(["html", "xml"]),
        )

    def render(self, report: RelatorioProjeto) -> str:
        template = self.env.get_template("base.html")
        return template.render(
            titulo="Preview do Relatório Institucional",
            metadata=report.metadata,
            total_metas=report.total_metas,
            total_atividades=report.total_atividades,
            metas=report.itensmetaatividade[:2],
        )
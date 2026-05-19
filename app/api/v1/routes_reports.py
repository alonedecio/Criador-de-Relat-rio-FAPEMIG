from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse

from app.core.config import DEFAULT_REPORT_FILE
from app.domain.reporting.assembler import ReportAssembler
from app.domain.rendering.html_report import HTMLReportRenderer

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/preview", response_class=HTMLResponse)
def preview_report():
    assembler = ReportAssembler()
    renderer = HTMLReportRenderer()

    report = assembler.from_file(DEFAULT_REPORT_FILE)
    html = renderer.render(report)
    return HTMLResponse(content=html)


@router.get("/raw", response_class=JSONResponse)
def raw_report():
    assembler = ReportAssembler()
    report = assembler.from_file(DEFAULT_REPORT_FILE)
    return JSONResponse(content=report.model_dump())
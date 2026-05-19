from fastapi import FastAPI
from app.api.v1.routes_reports import router as reports_router

app = FastAPI(title="Relatórios Institucionais", version="0.1.0")
app.include_router(reports_router, prefix="/api/v1")
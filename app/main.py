from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.ui.routes import router as ui_router
from app.workflows.kt_workflow import router as kt_workflow_router


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Local MVP for the full Knowledge Transfer Agent workflow.",
)

static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")

app.include_router(ui_router)
app.include_router(kt_workflow_router)


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}

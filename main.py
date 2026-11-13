from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from config import BASE_DIR
from database import get_engine
from routers.auth import router as auth_router
from routers.chats import router as chats_router
from routers.jobs import router as jobs_router
from routers.pipelines import router as pipelines_router
from routers.runs import router as runs_router
from routers.system import router as system_router

app = FastAPI(title="NIRS — сборки мобильного клиента")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
app.include_router(chats_router)
app.include_router(pipelines_router)
app.include_router(runs_router)
app.include_router(auth_router)
app.include_router(jobs_router)
app.include_router(system_router)


@app.middleware("http")
async def response_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    if request.url.path.startswith(("/api/", "/auth/")):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/")
def main_page():
    return FileResponse(BASE_DIR / "templates/main_page.html")


@app.get("/health/live", tags=["Health"])
def liveness():
    return {"status": "ok"}


@app.get("/health/ready", tags=["Health"])
def readiness():
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
            # Readiness includes the schema, not only TCP/database availability.
            import models

            for table in models.User.metadata.sorted_tables:
                connection.execute(table.select().limit(0))
    except SQLAlchemyError:
        return JSONResponse(status_code=503, content={"status": "unavailable"})
    return {"status": "ok"}

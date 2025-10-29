# api/app.py
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
import mimetypes

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from src.config import get_settings
from src.utils.logger import get_logger
from src.api import endpoints  

logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ---- startup ----
    logger.info("🚀 API starting up")
    yield
    # ---- shutdown ----
    logger.info("🛑 API shutting down")

def create_app() -> FastAPI:

    app = FastAPI(
        title="Document Ingestion API",
        description="Upload documents and ingest into Qdrant via LangChain.",
        version="1.0.0",
        lifespan=lifespan,
    )

    # ---------- CORS ----------
    # Pull from env if set, else sensible local defaults
    default_origins = [
        "http://localhost",
        "http://localhost:8080",
        "http://localhost:8081",
        "http://127.0.0.1",
        "http://127.0.0.1:8080",
        "http://127.0.0.1:8081",
    ]
    allow_origins = default_origins  # or parse from settings if you add one
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ---------- Static (optional) ----------
    # Mount only if the folder exists (avoids container path issues)
    static_root = Path("/app")
    if static_root.exists():
        app.mount("/static", StaticFiles(directory=str(static_root)), name="static")


    # ---------- Routers ----------
   # src/api/app.py
    app.include_router(endpoints.router)

    # ---------- Health ----------
    @app.get("/", tags=["Health"])
    def root():
        return {"status": "ok", "message": "Welcome to the Document Ingestion API!"}

    @app.get("/healthz", tags=["Health"])
    def healthz():
        return {"status": "ok"}

    return app

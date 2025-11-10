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
from src.api.endpoints import auth_router, ingestion_router

logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ---- startup ----
    logger.info("🚀 API starting up")
    yield
    # ---- shutdown ----
    logger.info("🛑 API shutting down")

def create_app() -> FastAPI:
    # Create FastAPI app with all configurations
    app = FastAPI(
        title="Document Ingestion API",
        description="Upload documents and ingest into Qdrant via LangChain.",
        version="1.0.0",
        lifespan=lifespan
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # For development - update for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount static files from frontend directory
    frontend_path = Path(__file__).parent.parent.parent / "frontend"
    if frontend_path.exists():
        app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="frontend")

    # Include routers
    app.include_router(auth_router)
    app.include_router(ingestion_router)

    # Health check endpoints
    @app.get("/healthz", tags=["Health"])
    def healthz():
        return {"status": "ok"}
        
    return app

    return app

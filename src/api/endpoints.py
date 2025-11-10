# api/endpoints.py
from __future__ import annotations

from functools import lru_cache
import asyncio
import io
import os
import uuid
import zipfile
import hashlib
import mimetypes 
from pathlib import Path
from typing import List, Optional, AsyncGenerator, Dict

from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException, Header, status, Query, Depends
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
from fastapi.security import HTTPBearer
from enum import Enum
from pydantic import BaseModel

from src.utils.logger import get_logger
from src.core.agent import retrieval_agent, StreamingRAGResponse
from src.ingestion.orchestrator import AgenticIngestionOrchestrator
from src.core.tools import TitleGenerator
from src.api.auth import (
    UserLogin,
    UserResponse,
    verify_password,
    create_access_token,
    get_current_user,
    USERS
)

# Create separate routers for different endpoint groups
auth_router = APIRouter(prefix="/v1/auth", tags=["Authentication"])
ingestion_router = APIRouter(prefix="/v1", tags=["Ingestion"])
logger = get_logger(__name__)

# Authentication endpoints
@auth_router.post("/login", response_model=UserResponse)
async def login(user_data: UserLogin):
    if user_data.email not in USERS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    stored_password_hash = USERS[user_data.email]
    if not verify_password(user_data.password, stored_password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    access_token = create_access_token(user_data.email)
    return {"email": user_data.email, "token": access_token}

@auth_router.get("/me")
async def read_users_me(current_user: str = Depends(get_current_user)):
    return {"email": current_user}

class JobStatus(str, Enum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    DUPLICATE = "DUPLICATE"

# In-memory store for job statuses
JOB_STATUSES: Dict[str, Dict[str, str]] = {}

# ------------------------ Config ------------------------

ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "text/plain",
    "text/markdown",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
}
MAX_UPLOAD_SIZE_MB = 100
MAX_ZIP_SIZE_MB = 500
MAX_FILES_PER_ZIP = 500

# ------------------------ Models ------------------------

class JobInfo(BaseModel):
    job_id: str
    file_name: str
    saved_path: str
    sha256: str

class UploadResponse(BaseModel):
    message: str
    jobs: List[JobInfo]

class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    file_name: str
    progress: str = "0"  # Keep as string for consistency with frontend
    current_step: str = ""

class HealthResponse(BaseModel):
    status: str = "ok"

class TitleResponse(BaseModel):
    title: str

# ------------------------ Helpers ------------------------

def _dirs() -> tuple[Path, Path]:
    root = Path.cwd()
    uploads = root / "data" / "uploads"
    figures = root / "figures"
    uploads.mkdir(parents=True, exist_ok=True)
    figures.mkdir(parents=True, exist_ok=True)
    return uploads, figures

def _safe_name(name: str) -> str:
    return os.path.basename(name).replace("\x00", "")

def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def _sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def _limit(raw: bytes, mb: int, label: str):
    if len(raw) > mb * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            detail=f"{label} exceeds {mb} MB")

def _check_type(up: UploadFile):
    if up.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                            detail=f"Unsupported content type: {up.content_type}")

def _zip_safe_path(root: Path, member: str) -> Path:
    target = (root / _safe_name(os.path.basename(member))).resolve()
    if not str(target).startswith(str(root.resolve())):
        raise HTTPException(status_code=400, detail="Unsafe path in ZIP")
    return target

@lru_cache(maxsize=1)
def get_title_generator() -> TitleGenerator:

    """

    Dependency injector for the TitleGenerator.

    Uses lru_cache to ensure a single instance is created.

    """

    return TitleGenerator()

# --- MODIFIED: Background task is now async and uses the orchestrator ---
async def _process_bg(job_id: str, doc_path: str, figures_dir: str, file_name: str):
    """Asynchronous background task to process a single document via the orchestrator."""
    try:
        JOB_STATUSES[job_id] = {
            "job_id": job_id,
            "status": JobStatus.PROCESSING,
            "file_name": file_name,
            "progress": "0",
            "current_step": "Starting document processing"
        }
        logger.info(f"[BG] Orchestrator starting for: {doc_path}")
        
        # Update progress for duplicate check
        JOB_STATUSES[job_id].update({
            "job_id": job_id,
            "progress": "10",
            "current_step": "Checking for duplicates"
        })
        
        # Instantiate and run the agentic orchestrator
        orchestrator = AgenticIngestionOrchestrator(doc_path, figures_dir)
        
        def progress_callback(step: str, progress: int):
            if job_id in JOB_STATUSES:
                JOB_STATUSES[job_id].update({
                    "job_id": job_id,
                    "progress": str(progress),
                    "current_step": step
                })
        
        was_processed = await orchestrator.run(progress_callback)
        
        if was_processed:
            status_update = {
                "job_id": job_id,
                "status": JobStatus.SUCCESS,
                "progress": "100",
                "current_step": "Document successfully processed"
            }
            JOB_STATUSES[job_id].update(status_update)
            logger.info(f"[BG] Orchestrator finished for: {doc_path}")
            # Keep status for 1 minute
            await asyncio.sleep(60)
            if job_id in JOB_STATUSES and JOB_STATUSES[job_id]["status"] == JobStatus.SUCCESS:
                del JOB_STATUSES[job_id]
        else:
            status_update = {
                "job_id": job_id,
                "status": JobStatus.DUPLICATE,
                "progress": "100",
                "current_step": "Document already exists in database"
            }
            JOB_STATUSES[job_id].update(status_update)
            logger.info(f"[BG] File already exists in database: {doc_path}")
            # Keep status for 1 minute
            await asyncio.sleep(60)
            if job_id in JOB_STATUSES and JOB_STATUSES[job_id]["status"] == JobStatus.DUPLICATE:
                del JOB_STATUSES[job_id]
    except Exception as e:
        logger.error(f"[BG] Error processing {doc_path}: {e}", exc_info=True)
        if job_id in JOB_STATUSES:
            status_update = {
                "job_id": job_id,
                "status": JobStatus.FAILED,
                "progress": "0",
                "current_step": f"Error: {str(e)}"
            }
            JOB_STATUSES[job_id].update(status_update)
            # Keep status for 1 minute
            await asyncio.sleep(60)
            if job_id in JOB_STATUSES and JOB_STATUSES[job_id]["status"] == JobStatus.FAILED:
                del JOB_STATUSES[job_id]

# ------------------------ Endpoints ------------------------

@ingestion_router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()

@ingestion_router.get("/job-status/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str, current_user: str = Depends(get_current_user)):
    """Get the status of a specific upload job."""
    if job_id not in JOB_STATUSES:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    
    status = JOB_STATUSES[job_id]
    logger.info(f"Status request for job {job_id}: {status}")
    return JobStatusResponse(**status)

@ingestion_router.post("/upload-documents", response_model=UploadResponse)
async def upload_documents(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(..., description="PDF/TXT/MD/DOCX"),
    current_user: str = Depends(get_current_user),
):
    try:
        uploads_dir, figures_dir = _dirs()
        jobs: List[JobInfo] = []

        for up in files:
            _check_type(up)
            raw = await up.read()
            await up.close()
            _limit(raw, MAX_UPLOAD_SIZE_MB, f"File {up.filename}")

            sha = _sha256_bytes(raw)
            subdir = uploads_dir / sha[:8]
            subdir.mkdir(parents=True, exist_ok=True)

            saved = subdir / f"{_safe_name(up.filename)}"
            saved.write_bytes(raw)

            job_id = uuid.uuid4().hex
            safe_filename = _safe_name(up.filename)
            JOB_STATUSES[job_id] = {
                "job_id": job_id,
                "status": JobStatus.QUEUED, 
                "file_name": safe_filename,
                "progress": "0",
                "current_step": "Queued for processing"
            }
            
            # FastAPI correctly handles adding async functions as background tasks
            background_tasks.add_task(_process_bg, job_id, str(saved), str(figures_dir), safe_filename)

            jobs.append(JobInfo(job_id=job_id, file_name=safe_filename,
                                saved_path=str(saved), sha256=sha))
            logger.info(f"Queued {job_id} for {safe_filename} ({sha[:12]}...)")

        if not jobs:
            raise HTTPException(status_code=400, detail="No valid files uploaded.")
        return UploadResponse(message=f"{len(jobs)} file(s) queued.", jobs=jobs)
    except Exception as e:
        logger.error(f"Error during document upload: {e}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An unexpected error occurred during file upload."},
        )

@ingestion_router.post("/upload-zip", response_model=UploadResponse)
async def upload_zip(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="ZIP with allowed files"),
    current_user: str = Depends(get_current_user),
):
    uploads_dir, figures_dir = _dirs()
    raw_zip = await file.read()
    await file.close()
    _limit(raw_zip, MAX_ZIP_SIZE_MB, "ZIP")

    try:
        zf = zipfile.ZipFile(io.BytesIO(raw_zip))
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Corrupted ZIP")

    jobs: List[JobInfo] = []
    batch_root = uploads_dir / f"zip_{uuid.uuid4().hex}"
    batch_root.mkdir(parents=True, exist_ok=True)

    try:
        infos = zf.infolist()
        if len(infos) > MAX_FILES_PER_ZIP:
            raise HTTPException(status_code=400, detail=f"ZIP has > {MAX_FILES_PER_ZIP} entries")

        for info in infos:
            if info.is_dir(): continue
            name = info.filename.lower()
            if not (name.endswith(".pdf") or name.endswith(".txt") or name.endswith(".md") or name.endswith(".docx")):
                continue

            target = _zip_safe_path(batch_root, info.filename)
            with zf.open(info) as src, target.open("wb") as dst:
                content = src.read()
                _limit(content, MAX_UPLOAD_SIZE_MB, f"File {info.filename} in ZIP")
                dst.write(content)

            sha = _sha256_file(target)
            job_id = uuid.uuid4().hex
            safe_filename = _safe_name(info.filename)
            JOB_STATUSES[job_id] = {
                "job_id": job_id,
                "status": JobStatus.QUEUED, 
                "file_name": safe_filename,
                "progress": "0",
                "current_step": "Queued for processing"
            }
            background_tasks.add_task(_process_bg, job_id, str(target), str(figures_dir), safe_filename)

            jobs.append(JobInfo(job_id=job_id, file_name=safe_filename,
                                saved_path=str(target), sha256=sha))
            logger.info(f"Queued {job_id} for {safe_filename} ({sha[:12]}...)")
    finally:
        zf.close()

    if not jobs:
        raise HTTPException(status_code=400, detail="No valid files found in ZIP.")
    return UploadResponse(message=f"{len(jobs)} file(s) queued from ZIP.", jobs=jobs)


# ------------------------ Query Endpoints ------------------------
import json

class QueryRequest(BaseModel):
    query: str

# === Endpoint 1: Rich, Non-Streaming (Invoke) ===
@ingestion_router.post("/query/invoke", summary="Get a final answer with sources (non-streaming)")
async def query_invoke_endpoint(request: QueryRequest, current_user: str = Depends(get_current_user)):
    """
    Receives a query and returns a single JSON response containing the complete
    answer and the source documents. This is a non-streaming, "invoke" style endpoint.
    """
    if not request.query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
    try:
        # The agent's run method handles the entire workflow
        streaming_response: StreamingRAGResponse = retrieval_agent.run(request.query)
        
        # Consume the stream to get the final response object
        response_data = streaming_response.get_response()
        
        sources = []
        for node in response_data["source_nodes"]:
            md = node.metadata or {}
            source_data = {
                "type": md.get("element_type"),
                "file_name": md.get("file_name"),
                "page_number": md.get("page_number"),
                "content": md.get("table_html") if md.get("element_type") == "table" else None,
                "image_path": os.path.basename(md.get("image_path")) if md.get("element_type") == "image" and md.get("image_path") else None,
            }
            sources.append(source_data)
        
        rich_response = {
            "answer": response_data["response"],
            "sources": sources
        }
        return JSONResponse(content=rich_response)
    except Exception as e:
        logger.error(f"Error in /query/invoke endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An error occurred: {e}")


# === Endpoint 2: Simple Text Streaming ===
async def stream_text_generator(response: StreamingRAGResponse) -> AsyncGenerator[str, None]:
    """Generator for the simple text streaming response."""
    for token in response.response_gen:
        yield token

@ingestion_router.post("/query/stream-text", summary="Get a simple streaming text answer")
async def query_stream_text_endpoint(request: QueryRequest, current_user: str = Depends(get_current_user)):
    """
    Receives a query and returns a simple streaming text response (media_type="text/plain").
    """
    if not request.query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
    try:
        # Use the unified retrieval agent
        streaming_response = retrieval_agent.run(request.query)
        return StreamingResponse(stream_text_generator(streaming_response), media_type="text/plain")
    except Exception as e:
        logger.error(f"Error in /query/stream-text endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An error occurred: {e}")


# === Endpoint 3: Rich, Streaming (Server-Sent Events) ===
async def stream_rich_generator(response: StreamingRAGResponse) -> AsyncGenerator[str, None]:
    """
    Generator for the rich streaming response using Server-Sent Events (SSE).
    Yields events for sources, tokens, and the end of the stream.
    """
    # 1. Yield a 'sources' event with all source documents
    sources = []
    for node in response.source_nodes:
        md = node.metadata or {}
        sources.append({
            "type": md.get("element_type"),
            "file_name": md.get("file_name"),
            "page_number": md.get("page_number"),
            "content": md.get("table_html") if md.get("element_type") == "table" else None,
            "image_path": os.path.basename(md.get("image_path")) if md.get("element_type") == "image" and md.get("image_path") else None,
        })
    
    # The data field must be a string, so we dump the list to a JSON string
    sources_json = json.dumps(sources)
    yield f"event: sources\ndata: {sources_json}\n\n"

    # 2. Yield 'token' events for each piece of the answer
    for token in response.response_gen:
        # Escape newlines in the token data to conform to the SSE spec
        data = json.dumps(token)
        yield f"event: token\ndata: {data}\n\n"

    # 3. Yield an 'end' event to signal completion
    yield "event: end\ndata: Stream ended\n\n"

@ingestion_router.get("/query/stream-rich", summary="Get a rich streaming answer with sources (SSE)")
async def query_stream_rich_endpoint(query: str = Query(..., min_length=1), current_user: str = Depends(get_current_user)):
    """
    Receives a query via URL parameter and returns a rich streaming response
    using Server-Sent Events. This endpoint is designed for use with EventSource.
    Events include:
    - `sources`: A single event containing all source document metadata.
    - `token`: A series of events, each containing a piece of the answer.
    - `end`: A final event to signal the end of the stream.
    """
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
    try:
        streaming_response = retrieval_agent.run(query)
        return StreamingResponse(stream_rich_generator(streaming_response), media_type="text/event-stream")
    except Exception as e:
        logger.error(f"Error in /query/stream-rich endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An error occurred: {e}")

@ingestion_router.post("/query/summarize", response_model=TitleResponse)
async def summarize_query_endpoint(
    request: QueryRequest,
    title_generator: TitleGenerator = Depends(get_title_generator),
    current_user: str = Depends(get_current_user)
):
    """
    Receives a query and returns a three-word title.
    """
    if not request.query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
    try:
        title = await title_generator.generate(request.query)
        return TitleResponse(title=title)
    except Exception as e:
        logger.error(f"Error in /query/summarize endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An error occurred: {e}")

@ingestion_router.get("/image", summary="Serve an image from the figures directory")
async def get_image(path: str = Query(..., description="The filename of the image to retrieve"), current_user: str = Depends(get_current_user)):
    """
    Serves an image from the 'figures' directory. This endpoint is protected
    against directory traversal attacks.
    """
    try:
        _, figures_dir = _dirs()
        
        # Security: Sanitize filename and prevent directory traversal
        safe_filename = _safe_name(path)
        if ".." in safe_filename or safe_filename.startswith("/"):
            raise HTTPException(status_code=400, detail="Invalid filename.")
            
        image_path = figures_dir / safe_filename
        
        if not image_path.is_file():
            logger.warning(f"Image not found at path: {image_path}")
            raise HTTPException(status_code=404, detail="Image not found.")
        
        # Infer MIME type from filename
        mime_type, _ = mimetypes.guess_type(image_path)
        if not mime_type or not mime_type.startswith("image/"):
            mime_type = "application/octet-stream" # Fallback
            
        return FileResponse(str(image_path), media_type=mime_type)
        
    except HTTPException as http_exc:
        # Re-raise HTTP exceptions to let FastAPI handle them
        raise http_exc
    except Exception as e:
        logger.error(f"Error serving image '{path}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An internal error occurred while serving the image.")

@ingestion_router.get("/pdf", summary="Serve a PDF from the uploads directory")
async def get_pdf(path: str = Query(..., description="The sha256 subfolder and filename of the PDF to retrieve"), current_user: str = Depends(get_current_user)):
    """
    Serves a PDF file from the uploads directory. This endpoint is protected
    against directory traversal attacks.
    
    The path should be in the format: "<sha256_subfolder>/<filename>"
    Example: "83beb169/document.pdf"
    """
    try:
        uploads_dir, _ = _dirs()
        
        # Validate path format
        path_parts = path.split('/')
        if len(path_parts) != 2:
            raise HTTPException(
                status_code=400, 
                detail="Invalid path format. Expected format: '<sha256_subfolder>/<filename>'"
            )
            
        subfolder, filename = path_parts
        
        # Security: Sanitize path components and prevent directory traversal
        safe_subfolder = _safe_name(subfolder)
        safe_filename = _safe_name(filename)
        
        if not safe_subfolder or not safe_filename or \
           ".." in safe_subfolder or ".." in safe_filename or \
           safe_subfolder.startswith("/") or safe_filename.startswith("/"):
            raise HTTPException(status_code=400, detail="Invalid path components.")
            
        # Validate subfolder is exactly 8 hex characters (sha256 prefix)
        if not subfolder.strip() or len(subfolder.strip()) != 8 or not all(c in '0123456789abcdefABCDEF' for c in subfolder.strip()):
            raise HTTPException(
                status_code=400, 
                detail="Invalid sha256 subfolder. Must be exactly 8 hexadecimal characters."
            )
            
        # Construct and validate the full path
        pdf_path = uploads_dir / safe_subfolder / safe_filename
        
        if not pdf_path.exists():
            logger.warning(f"PDF not found: {pdf_path}")
            raise HTTPException(status_code=404, detail="PDF not found")
            
        if not pdf_path.is_file():
            raise HTTPException(status_code=400, detail="Path is not a file")
            
        # Verify file is actually a PDF
        mime_type, _ = mimetypes.guess_type(pdf_path)
        if mime_type != "application/pdf":
            raise HTTPException(status_code=400, detail="File is not a PDF")
            
        logger.info(f"Serving PDF: {pdf_path}")
        return FileResponse(str(pdf_path), media_type="application/pdf")
        
    except HTTPException as http_exc:
        # Re-raise HTTP exceptions to let FastAPI handle them
        raise http_exc
    except Exception as e:
        logger.error(f"Error serving PDF '{path}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An internal error occurred while serving the PDF")
    """
    try:
        uploads_dir, _ = _dirs()
        
        # Security: Sanitize path components and prevent directory traversal
        path_parts = path.split('/')
        if len(path_parts) != 2:
            raise HTTPException(status_code=400, detail="Invalid path format. Expected format: '<sha256_subfolder>/<filename>'")
            
        subfolder, filename = path_parts
        safe_subfolder = _safe_name(subfolder)
        safe_filename = _safe_name(filename)
        
        if ".." in safe_subfolder or ".." in safe_filename or \
           safe_subfolder.startswith("/") or safe_filename.startswith("/"):
            raise HTTPException(status_code=400, detail="Invalid path.")
            
        pdf_path = uploads_dir / safe_subfolder / safe_filename
        
        if not pdf_path.is_file():
            logger.warning(f"PDF not found at path: {pdf_path}")
            raise HTTPException(status_code=404, detail="PDF not found.")
        
        # Verify file is actually a PDF
        mime_type, _ = mimetypes.guess_type(pdf_path)
        if mime_type != "application/pdf":
            raise HTTPException(status_code=400, detail="File is not a PDF.")
            
        return FileResponse(str(pdf_path), media_type="application/pdf")
        
    except HTTPException as http_exc:
        # Re-raise HTTP exceptions to let FastAPI handle them
        raise http_exc
    except Exception as e:
        logger.error(f"Error serving PDF '{path}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An internal error occurred while serving the PDF.")
        """
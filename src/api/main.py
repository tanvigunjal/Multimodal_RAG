# api/main.py
import uvicorn
from src.api.app import create_app
from src.utils.logger import configure_logging, get_logger

# Configure logging before any other operations
configure_logging()
logger = get_logger(__name__)

app = create_app()

if __name__ == "__main__":
    # Local/dev run. For production, prefer gunicorn/uvicorn workers (see below).
    logger.info("Starting development server...")
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000, reload=True)

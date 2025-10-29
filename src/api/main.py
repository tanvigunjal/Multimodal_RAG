# api/main.py
import uvicorn
from src.api.app import create_app

app = create_app()

if __name__ == "__main__":
    # Local/dev run. For production, prefer gunicorn/uvicorn workers (see below).
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000, reload=True)

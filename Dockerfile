# # Stage 1: Builder stage with build-time dependencies
# FROM python:3.10-bookworm AS builder

# # Set the working directory
# WORKDIR /app

# # Install system-level dependencies required for building Python packages
# RUN apt-get update && apt-get install -y --no-install-recommends \
#     build-essential \
#     poppler-utils \
#     tesseract-ocr \
#     libgl1-mesa-glx \
#     python3-dev \
#     libffi-dev \
#     && apt-get clean && rm -rf /var/lib/apt/lists/*

# # Copy only the requirements file to leverage Docker cache
# COPY requirements.txt .

# # Upgrade pip and install Python dependencies
# RUN pip install --upgrade pip && \
#     pip install --no-cache-dir --prefix=/install -r requirements.txt

# # ---

# # Stage 2: Final lightweight production image
# FROM python:3.10-slim-bookworm

# # Set the working directory
# WORKDIR /app


# # Create a non-root user and group with a home directory
# RUN groupadd -r appuser && useradd -r -m -g appuser appuser

# # Install only runtime system-level dependencies
# RUN apt-get update && apt-get install -y --no-install-recommends \
#     poppler-utils \
#     tesseract-ocr \
#     libgl1-mesa-glx \
#     curl \
#     && apt-get clean && rm -rf /var/lib/apt/lists/*

# # Copy installed Python packages from the builder stage
# COPY --from=builder /install /usr/local

# # Set environment variables to prevent permission errors
# ENV HOME=/home/appuser
# ENV MPLCONFIGDIR=/tmp/matplotlib

# # Copy the application source code
# COPY src ./src

# RUN mkdir -p /app/data/uploads /app/figures && \
#     chown -R appuser:appuser /app

# # Change ownership of the app directory
# RUN chown -R appuser:appuser /app

# # Switch to the non-root user
# USER appuser

# # Pre-download NLTK data as appuser to avoid runtime downloads
# RUN python3 -c "import nltk; \
#     nltk.download('averaged_perceptron_tagger_eng', quiet=True, download_dir='/home/appuser/nltk_data'); \
#     nltk.download('punkt', quiet=True, download_dir='/home/appuser/nltk_data'); \
#     nltk.download('punkt_tab', quiet=True, download_dir='/home/appuser/nltk_data')" || true


# # Expose the port the app runs on
# EXPOSE 8000

# # The command to run when the container starts
# CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]


# Stage 1: Builder stage with build-time dependencies
FROM python:3.10-bookworm AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    poppler-utils \
    tesseract-ocr \
    libgl1-mesa-glx \
    python3-dev \
    libffi-dev \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --upgrade pip && \
    pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---

# Stage 2: Final lightweight production image
FROM python:3.10-slim-bookworm

WORKDIR /app

# Create non-root user with specific UID/GID for consistency
RUN groupadd -r -g 1000 appuser && useradd -r -m -u 1000 -g appuser appuser

RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    tesseract-ocr \
    libgl1-mesa-glx \
    curl \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local

ENV HOME=/home/appuser \
    MPLCONFIGDIR=/tmp/matplotlib \
    NLTK_DATA=/home/appuser/nltk_data

# Create directories and set ownership
RUN mkdir -p /app/data/uploads /app/figures /home/appuser/nltk_data /tmp/matplotlib && \
    chown -R appuser:appuser /app /home/appuser /tmp/matplotlib

COPY --chown=appuser:appuser src ./src

USER appuser

RUN python3 -c "import nltk; \
    nltk.download('averaged_perceptron_tagger_eng', quiet=True, download_dir='/home/appuser/nltk_data'); \
    nltk.download('punkt', quiet=True, download_dir='/home/appuser/nltk_data'); \
    nltk.download('punkt_tab', quiet=True, download_dir='/home/appuser/nltk_data')" || true

EXPOSE 8000

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
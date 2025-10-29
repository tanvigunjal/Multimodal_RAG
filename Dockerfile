# Stage 1: Builder stage with build-time dependencies
FROM python:3.10-bookworm AS builder

# Set the working directory
WORKDIR /app

# Install system-level dependencies required for building Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    poppler-utils \
    tesseract-ocr \
    libgl1-mesa-glx \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy only the requirements file to leverage Docker cache
COPY requirements.txt .

# Upgrade pip and install Python dependencies
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---

# Stage 2: Final lightweight production image
FROM python:3.10-slim-bookworm

# Set the working directory
WORKDIR /app

# Create a non-root user and group with a home directory
RUN groupadd -r appuser && useradd -r -m -g appuser appuser

# Install only runtime system-level dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    tesseract-ocr \
    libgl1-mesa-glx \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from the builder stage
COPY --from=builder /install /usr/local

# Set environment variables to prevent permission errors
ENV HOME=/home/appuser
ENV MPLCONFIGDIR=/tmp/matplotlib

# Copy the application source code
COPY src ./src

# Change ownership of the app directory
RUN chown -R appuser:appuser /app

# Switch to the non-root user
USER appuser

# Expose the port the app runs on
EXPOSE 8000

# The command to run when the container starts
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

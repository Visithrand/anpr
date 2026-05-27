# ==============================================================================
# ANPR.OS — Backend API Dockerfile
# ==============================================================================
# Multi-stage build for a lean production image.
# Runs the FastAPI backend with uvicorn.
# ==============================================================================

FROM python:3.11-slim AS base

# Prevent Python from writing .pyc and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# System dependencies required by OpenCV, OpenVINO, and psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libgl1-mesa-dri \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user for security
RUN groupadd -r anpr && useradd -r -g anpr -m anpr

WORKDIR /app

# ---------------------------------------------------------------------------
# Dependencies layer (cached unless requirements.txt changes)
# ---------------------------------------------------------------------------
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ---------------------------------------------------------------------------
# Application layer
# ---------------------------------------------------------------------------
COPY . .

# Create required directories
RUN mkdir -p logs static/plates snapshots && \
    chown -R anpr:anpr /app

# Switch to non-root user
USER anpr

# Expose the API port
EXPOSE 8000

# Health check — uses the /system/health endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import httpx; r = httpx.get('http://localhost:8000/system/health', timeout=5); exit(0 if r.status_code == 200 else 1)" || exit 1

# Production server
CMD ["uvicorn", "backend.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1", \
     "--log-level", "info", \
     "--timeout-keep-alive", "65"]

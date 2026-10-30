# --- runtime image -----------------------------------------------------------
FROM python:3.12-slim

# Reproducible builds: no .pyc files, unbuffered logs so `docker logs` shows
# uvicorn output immediately.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencies first, alone, so this layer is cached until requirements change.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code, including the committed data snapshot.
COPY core ./core
COPY scripts ./scripts
COPY tests ./tests
COPY conftest.py .
COPY main.py .
COPY data ./data

# Run as a non-root user; the app only needs read access.
RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8000

# /api/health is the container healthcheck target used by docker-compose.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

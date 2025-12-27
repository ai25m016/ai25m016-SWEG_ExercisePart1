# 🔹 1. Basis-Image
FROM python:3.12-slim

# 🔹 2. Optional: System-Tools für evtl. Build-Abhängigkeiten
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
 && rm -rf /var/lib/apt/lists/*

# 🔹 3. uv installieren (wie lokal)
RUN pip install --no-cache-dir uv

# 4. Arbeitsverzeichnis im Container
WORKDIR /app/backend

# 5. Dateien für Dependency-Installation kopieren
COPY backend/pyproject.toml backend/uv.lock ./

# 👇 NEU: README dahin kopieren, wo pyproject es erwartet (../README.md)
COPY README.md /app/README.md

# 6. Dependencies installieren (reproduzierbar, wie auf deinem Rechner)
RUN uv sync --frozen --no-editable

# 7. Restlichen Backend-Code kopieren
COPY backend ./

# 8. Port der API
EXPOSE 8000

# 9. Startkommando – Uvicorn direkt starten
CMD ["uv", "run", "uvicorn", "simple_social_backend.api:app", "--host", "0.0.0.0", "--port", "8000"]



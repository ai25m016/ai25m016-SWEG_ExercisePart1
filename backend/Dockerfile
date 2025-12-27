FROM python:3.12-slim
WORKDIR /app/backend

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
 && rm -rf /var/lib/apt/lists/*

# README ins Root, weil pyproject readme = "../README.md"
COPY README.md /app/README.md

# caching: erst Metadaten + Source
COPY backend/pyproject.toml ./
COPY backend/src/ ./src/

RUN pip install --no-cache-dir -U pip \
 && pip install --no-cache-dir .

# restliche backend files (tests, env, migrations, etc.)
COPY backend/ ./

EXPOSE 8000
CMD ["social-api"]

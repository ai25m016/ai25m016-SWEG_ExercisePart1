FROM python:3.12-slim

WORKDIR /app/text_gen

# Build backend for building the package (hatchling)
RUN pip install --no-cache-dir hatchling

# Install the textgen package (console script: social-textgen)
COPY pyproject.toml ./
COPY src ./src

ENV PIP_DEFAULT_TIMEOUT=300

# CPU-only torch (viel kleiner/ohne CUDA-Dependencies)
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch==2.2.2

# dann dein Paket (transformers etc.)
RUN pip install --no-cache-dir .

CMD ["social-textgen"]

FROM python:3.12-slim

WORKDIR /app/image_resizer

# Build backend for building the package (hatchling)
RUN pip install --no-cache-dir hatchling

# Install the resizer package (console script: social-resizer)
COPY pyproject.toml ./
COPY src ./src

RUN pip install --no-cache-dir .

CMD ["social-resizer"]

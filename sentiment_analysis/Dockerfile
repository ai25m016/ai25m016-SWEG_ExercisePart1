FROM python:3.12-slim
WORKDIR /app

COPY pyproject.toml ./
COPY src/ ./src/

RUN pip install --no-cache-dir -U pip \
 && pip install --no-cache-dir .

COPY ./models/bert_clean.pth /app/model.pth
ENV MODEL_PATH=/app/model.pth

CMD ["social-sentiment"]

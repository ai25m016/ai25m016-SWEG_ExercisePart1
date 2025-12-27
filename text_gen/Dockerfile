FROM python:3.12-slim
WORKDIR /app/text_gen

COPY pyproject.toml ./
COPY src ./src

RUN pip install --no-cache-dir -U pip \
 && pip install --no-cache-dir .

CMD ["social-textgen"]

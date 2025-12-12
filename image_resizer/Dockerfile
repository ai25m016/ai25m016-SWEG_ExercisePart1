FROM python:3.12-slim

WORKDIR /app

# Abhängigkeiten, falls du Pillow / requests / pika brauchst
RUN pip install --no-cache-dir pika requests Pillow

COPY main.py .

CMD ["python", "main.py"]

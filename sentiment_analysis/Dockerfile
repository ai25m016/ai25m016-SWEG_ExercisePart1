FROM python:3.10-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your model file and code
# IMPORTANT: Place your .pth file in the sentiment_analysis folder!
COPY ./models/bert_clean.pth /app/model.pth
COPY main.py .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]

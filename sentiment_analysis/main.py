import os
import time
import json
import torch
import pika
import torch.nn as nn
import torch.nn.functional as F
from transformers import AutoTokenizer, BertModel

# --- CONFIGURATION ---
BASE_MODEL_NAME = "dbmdz/bert-base-german-cased"
MODEL_PATH = "/app/model.pth"
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
# We listen on this queue
RPC_QUEUE = "sentiment_rpc_queue"

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

# --- MODEL (Same as before) ---
class SentimentClassifier(nn.Module):
    def __init__(self, n_classes):
        super(SentimentClassifier, self).__init__()
        self.bert = BertModel.from_pretrained(BASE_MODEL_NAME)
        self.drop = nn.Dropout(p=0.3)
        self.out = nn.Linear(self.bert.config.hidden_size, n_classes)

    def forward(self, input_ids, attention_mask, token_type_ids=None):
        bert_output = self.bert(input_ids=input_ids, attention_mask=attention_mask)
        pooled_output = bert_output.pooler_output
        output = self.drop(pooled_output)
        return self.out(output)

# --- GLOBAL VARS ---
model = None
tokenizer = None
labels = {0: 'Negative', 1: 'Neutral', 2: 'Positive'}

def load_model():
    global model, tokenizer
    print("⏳ Loading BERT model...")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_NAME)
    model = SentimentClassifier(n_classes=3)
    model.load_state_dict(torch.load(MODEL_PATH, map_location=device))
    model.to(device)
    model.eval()
    print("✅ Model loaded!")

def predict(text):
    inputs = tokenizer(text, return_tensors="pt", truncation=True, padding=True, max_length=512)
    inputs = {k: v.to(device) for k, v in inputs.items()}
    with torch.no_grad():
        outputs = model(input_ids=inputs['input_ids'], attention_mask=inputs['attention_mask'])
        probabilities = F.softmax(outputs, dim=-1)
        pred = torch.argmax(probabilities, dim=-1).item()
    return labels[pred]

# --- RABBITMQ CONNECTION ---
def connect_rabbitmq():
    creds = pika.PlainCredentials(os.getenv("RABBITMQ_USER", "test"), os.getenv("RABBITMQ_PASSWORD", "test"))
    while True:
        try:
            return pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=creds, heartbeat=600))
        except Exception:
            time.sleep(2)

def main():
    load_model()
    connection = connect_rabbitmq()
    channel = connection.channel()
    
    # Declare the RPC queue
    channel.queue_declare(queue=RPC_QUEUE, durable=True)

    def on_request(ch, method, props, body):
        try:
            # 1. Parse Message
            msg = json.loads(body)
            text = msg.get('text', '')
            
            print(f"🔍 Analyzing: {text[:30]}...")
            sentiment = predict(text)
            print(f"👉 Result: {sentiment}")

            # 2. Prepare Response
            response = json.dumps({"sentiment": sentiment})

            # 3. Send Reply back to the "reply_to" queue
            ch.basic_publish(
                exchange='',
                routing_key=props.reply_to, # <--- Sending back to Backend
                properties=pika.BasicProperties(correlation_id=props.correlation_id),
                body=response
            )
            ch.basic_ack(delivery_tag=method.delivery_tag)
            
        except Exception as e:
            print(f"Error: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag)

    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=RPC_QUEUE, on_message_callback=on_request)
    print("🐰 Sentiment RPC Service Ready...")
    channel.start_consuming()

if __name__ == "__main__":
    time.sleep(5)
    main()

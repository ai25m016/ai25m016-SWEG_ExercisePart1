import json
import os
import uuid

try:
    import pika
except ImportError:
    pika = None 

# Queue Names
RESIZE_QUEUE = os.getenv("IMAGE_RESIZE_QUEUE", "image_resize")
SENTIMENT_RPC_QUEUE = "sentiment_rpc_queue" # Matches Sentiment Service
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")


# --- 1. EXISTING ASYNC FUNCTION (Keep this for Image Resize) ---
def publish_image_resize(post_id: int, image: str) -> None:
    if pika is None or os.getenv("DISABLE_QUEUE", "").lower() == "true": return
    
    creds = pika.PlainCredentials(os.getenv("RABBITMQ_USER", "test"), os.getenv("RABBITMQ_PASSWORD", "test"))
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=creds))
    channel = connection.channel()
    channel.queue_declare(queue=RESIZE_QUEUE, durable=True)
    
    body = json.dumps({"post_id": post_id, "image": image})
    channel.basic_publish(exchange="", routing_key=RESIZE_QUEUE, body=body, properties=pika.BasicProperties(delivery_mode=2))
    connection.close()


# --- 2. NEW RPC FUNCTION (Synchronous Wait) ---
class SentimentRpcClient:
    def __init__(self):
        self.creds = pika.PlainCredentials(os.getenv("RABBITMQ_USER", "test"), os.getenv("RABBITMQ_PASSWORD", "test"))
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=self.creds))
        self.channel = self.connection.channel()

        # Create a temporary exclusive callback queue for the answer
        result = self.channel.queue_declare(queue='', exclusive=True)
        self.callback_queue = result.method.queue

        self.channel.basic_consume(
            queue=self.callback_queue,
            on_message_callback=self.on_response,
            auto_ack=True
        )
        self.response = None
        self.corr_id = None

    def on_response(self, ch, method, props, body):
        if self.corr_id == props.correlation_id:
            self.response = body

    def call(self, text: str) -> str:
        self.response = None
        self.corr_id = str(uuid.uuid4())
        
        # Send text to Sentiment Service
        self.channel.basic_publish(
            exchange='',
            routing_key=SENTIMENT_RPC_QUEUE,
            properties=pika.BasicProperties(
                reply_to=self.callback_queue, # Tell them where to answer
                correlation_id=self.corr_id,
            ),
            body=json.dumps({"text": text}))
            
        # Wait specifically for the answer (Block until response)
        while self.response is None:
            self.connection.process_data_events()
            
        return json.loads(self.response)["sentiment"]

    def close(self):
        self.connection.close()

# Helper function to use easily in API
def check_sentiment_rpc(text: str) -> str:
    if os.getenv("DISABLE_QUEUE", "").lower() == "true": return "Neutral"
    client = SentimentRpcClient()
    try:
        result = client.call(text)
        return result
    finally:
        client.close()

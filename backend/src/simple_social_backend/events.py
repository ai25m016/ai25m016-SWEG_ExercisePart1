import json
import os
import uuid

try:
    import pika
except ImportError:
    pika = None


RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "test")
RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD", "test")

IMAGE_RESIZE_QUEUE = os.getenv("IMAGE_RESIZE_QUEUE", "image_resize")
TEXTGEN_QUEUE = os.getenv("TEXT_GENERATION_QUEUE", "text_generation")

# RPC queue for sentiment service
SENTIMENT_RPC_QUEUE = os.getenv("SENTIMENT_RPC_QUEUE", "sentiment_rpc_queue")


def _disabled() -> bool:
    return pika is None or os.getenv("DISABLE_QUEUE", "").lower() == "true"

def _get_channel():
    """
    Create a pika connection/channel with short timeouts so it does not block the web request indefinitely.
    """
    creds = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)

    # socket_timeout makes connect/read fail fast; connection_attempts=1 avoids long retry loops
    params = pika.ConnectionParameters(
        host=RABBITMQ_HOST,
        credentials=creds,
        heartbeat=60,
        blocked_connection_timeout=5,
        connection_attempts=1,
        socket_timeout=2,
    )

    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    return connection, channel

def _do_publish_image_resize(post_id: int, image: str) -> None:
    """
    Actually perform the publish. Runs in a background thread and swallows exceptions
    so the web request is not affected.
    """
    if pika is None or os.getenv("DISABLE_QUEUE", "").lower() == "true":
        return

    try:
        connection, channel = _get_channel()
        try:
            channel.queue_declare(queue=IMAGE_RESIZE_QUEUE, durable=True)
            body = json.dumps({"post_id": post_id, "image": image})
            channel.basic_publish(
                exchange="",
                routing_key=IMAGE_RESIZE_QUEUE,
                body=body.encode("utf-8"),
                properties=pika.BasicProperties(delivery_mode=2),
            )
        finally:
            try:
                connection.close()
            except Exception:
                pass
    except Exception as exc:
        # log the failure (print is fine for tests/CI), but do not raise
        print(f"[events] publish_image_resize failed (post_id={post_id}): {exc}")

# ----------------------------
# Async: Image Resize
# ----------------------------

def publish_image_resize(post_id: int, image: str) -> None:
    """
    Non-blocking API: schedule the actual publish in a background thread and return immediately.
    """
    if pika is None or os.getenv("DISABLE_QUEUE", "").lower() == "true":
        return

    # fire-and-forget: background thread will attempt the publish and log errors
    t = Thread(target=_do_publish_image_resize, args=(post_id, image), daemon=True)
    t.start()

# ----------------------------
# Async: Text Generation Job
# ----------------------------
def publish_textgen_job(job_id: int, prompt: str, max_new_tokens: int = 60) -> None:
    """
    Pre-Post Kommentarvorschlag (TextGenJob).
    """
    if _disabled():
        return

    connection, channel = _get_channel()
    channel.queue_declare(queue=TEXTGEN_QUEUE, durable=True)

    body = json.dumps(
        {
            "type": "job",
            "job_id": job_id,
            "prompt": prompt,
            "max_new_tokens": max_new_tokens,
        }
    ).encode("utf-8")

    channel.basic_publish(
        exchange="",
        routing_key=TEXTGEN_QUEUE,
        body=body,
        properties=pika.BasicProperties(delivery_mode=2),
    )
    connection.close()


# ----------------------------
# RPC: Sentiment Check
# ----------------------------
class SentimentRpcClient:
    def __init__(self):
        creds = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)
        params = pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=creds)
        self.connection = pika.BlockingConnection(params)
        self.channel = self.connection.channel()

        # exclusive callback queue for replies
        result = self.channel.queue_declare(queue="", exclusive=True)
        self.callback_queue = result.method.queue

        self.response = None
        self.corr_id = None

        self.channel.basic_consume(
            queue=self.callback_queue,
            on_message_callback=self.on_response,
            auto_ack=True,
        )

    def on_response(self, ch, method, props, body):
        if self.corr_id == props.correlation_id:
            self.response = body

    def call(self, text: str) -> str:
        self.response = None
        self.corr_id = str(uuid.uuid4())

        payload = json.dumps({"text": text}).encode("utf-8")

        self.channel.basic_publish(
            exchange="",
            routing_key=SENTIMENT_RPC_QUEUE,
            properties=pika.BasicProperties(
                reply_to=self.callback_queue,
                correlation_id=self.corr_id,
                delivery_mode=2,
            ),
            body=payload,
        )

        # block until response arrives
        while self.response is None:
            self.connection.process_data_events(time_limit=1)

        data = json.loads(self.response.decode("utf-8"))
        return data.get("sentiment", "Neutral")

    def close(self):
        self.connection.close()


def check_sentiment_rpc(text: str) -> str:
    """
    Synchronous sentiment check via RabbitMQ RPC.
    - If queues are disabled -> Neutral
    """
    if _disabled():
        return "Neutral"

    client = SentimentRpcClient()
    try:
        return client.call(text)
    finally:
        client.close()

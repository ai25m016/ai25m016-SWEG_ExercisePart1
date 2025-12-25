# backend/src/simple_social_backend/events.py
import json
import os
import uuid
import time
from threading import Thread

try:
    import pika
except ImportError:
    pika = None


def _env(name: str, default: str = "") -> str:
    v = os.getenv(name)
    return v if v is not None else default


def _disabled() -> bool:
    """
    Queues are disabled if:
    - pika isn't installed
    - DISABLE_QUEUE=true
    - RABBITMQ_HOST is missing or explicitly set to 'disabled'
      (your tests set this to avoid network calls)
    """
    if pika is None:
        return True

    if _env("DISABLE_QUEUE", "").lower() == "true":
        return True

    host = _env("RABBITMQ_HOST", "rabbitmq").strip().lower()
    if not host or host == "disabled":
        return True

    return False


def _get_rabbit_params() -> "pika.ConnectionParameters":
    host = _env("RABBITMQ_HOST", "rabbitmq")
    user = _env("RABBITMQ_USER", "test")
    password = _env("RABBITMQ_PASSWORD", "test")

    creds = pika.PlainCredentials(user, password)

    # Short timeouts & single attempt => fail fast, don't hang tests.
    return pika.ConnectionParameters(
        host=host,
        credentials=creds,
        heartbeat=60,
        blocked_connection_timeout=5,
        connection_attempts=1,
        socket_timeout=2,
    )


def _get_channel():
    """
    Create a pika connection/channel with short timeouts so it does not block callers indefinitely.
    """
    params = _get_rabbit_params()
    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    return connection, channel


def _safe_close(conn) -> None:
    try:
        conn.close()
    except Exception:
        pass


# ----------------------------
# Image Resize publish (non-blocking)
# ----------------------------

def _do_publish_image_resize(post_id: int, image: str) -> None:
    """
    Actually perform publishing. Runs in a background thread and swallows/logs exceptions.
    """
    if _disabled():
        return

    queue_name = _env("IMAGE_RESIZE_QUEUE", "image_resize")

    try:
        connection, channel = _get_channel()
        try:
            channel.queue_declare(queue=queue_name, durable=True)
            body = json.dumps({"post_id": post_id, "image": image}).encode("utf-8")
            channel.basic_publish(
                exchange="",
                routing_key=queue_name,
                body=body,
                properties=pika.BasicProperties(delivery_mode=2),
            )
        finally:
            _safe_close(connection)
    except Exception as exc:
        print(f"[events] publish_image_resize failed (post_id={post_id}): {exc}")


def publish_image_resize(post_id: int, image: str) -> None:
    """
    Non-blocking API: schedule the actual publish in a background thread and return immediately.
    If queues are disabled, it's a no-op.
    """
    if _disabled():
        return

    Thread(target=_do_publish_image_resize, args=(post_id, image), daemon=True).start()


# ----------------------------
# Text Generation publish (sync)
# ----------------------------

def publish_textgen_job(job_id: int, prompt: str, max_new_tokens: int = 60) -> None:
    """
    Publish a textgen job to the TEXT_GENERATION_QUEUE.

    If queues are disabled: no-op.
    If RabbitMQ is enabled but fails: raise, so API can mark the job as error.
    """
    if _disabled():
        return

    queue_name = _env("TEXT_GENERATION_QUEUE", "text_generation")

    connection = None
    try:
        connection, channel = _get_channel()
        channel.queue_declare(queue=queue_name, durable=True)
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
            routing_key=queue_name,
            body=body,
            properties=pika.BasicProperties(delivery_mode=2),
        )
    finally:
        if connection is not None:
            _safe_close(connection)


# ----------------------------
# RPC: Sentiment Check
# ----------------------------

class SentimentRpcClient:
    def __init__(self):
        if _disabled():
            raise RuntimeError("Queues disabled")

        params = _get_rabbit_params()
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

    def call(self, text: str, timeout_seconds: int = 5) -> str:
        rpc_queue = _env("SENTIMENT_RPC_QUEUE", "sentiment_rpc_queue")

        self.response = None
        self.corr_id = str(uuid.uuid4())

        payload = json.dumps({"text": text}).encode("utf-8")

        self.channel.basic_publish(
            exchange="",
            routing_key=rpc_queue,
            properties=pika.BasicProperties(
                reply_to=self.callback_queue,
                correlation_id=self.corr_id,
                delivery_mode=2,
            ),
            body=payload,
        )

        start_time = time.time()
        while self.response is None:
            self.connection.process_data_events(time_limit=1)
            if time.time() - start_time > timeout_seconds:
                raise TimeoutError("Sentiment RPC timed out (Service offline?)")

        data = json.loads(self.response.decode("utf-8"))
        return data.get("sentiment", "Neutral")

    def close(self):
        _safe_close(self.connection)


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

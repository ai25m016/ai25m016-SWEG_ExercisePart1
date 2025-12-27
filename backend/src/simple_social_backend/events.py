# backend/src/simple_social_backend/events.py
import json
import os
import time
import uuid
from threading import Thread
from typing import Optional, Tuple

try:
    import pika
except ImportError:
    pika = None


# -----------------------------------------------------------------------------
# Env
# -----------------------------------------------------------------------------
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "test")
RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD", "test")

IMAGE_RESIZE_QUEUE = os.getenv("IMAGE_RESIZE_QUEUE", "image_resize")
TEXTGEN_QUEUE = os.getenv("TEXT_GENERATION_QUEUE", "text_generation")
SENTIMENT_RPC_QUEUE = os.getenv("SENTIMENT_RPC_QUEUE", "sentiment_rpc_queue")


# -----------------------------------------------------------------------------
# Disable logic (IMPORTANT for tests / CI)
# -----------------------------------------------------------------------------
def _disabled() -> bool:
    """
    Queues are disabled if:
    - pika is not installed, OR
    - DISABLE_QUEUE=true, OR
    - RABBITMQ_HOST is set to a known "disabled" value (used in unit tests)
    """
    if pika is None:
        return True

    if os.getenv("DISABLE_QUEUE", "").strip().lower() == "true":
        return True

    host = (os.getenv("RABBITMQ_HOST", RABBITMQ_HOST) or "").strip().lower()
    if host in {"disabled", "off", "none", "no", "0"}:
        return True

    return False


def _require(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"Missing env var: {name}")
    return v

def _conn_params():
    host = os.getenv("RABBITMQ_HOST", RABBITMQ_HOST)
    user = os.getenv("RABBITMQ_USER", RABBITMQ_USER)
    pw   = os.getenv("RABBITMQ_PASSWORD", RABBITMQ_PASSWORD)
    creds = pika.PlainCredentials(user, pw)
    return pika.ConnectionParameters(
        host=host,
        credentials=creds,
        heartbeat=30,
        blocked_connection_timeout=5,
        connection_attempts=1,
        retry_delay=0.0,
        socket_timeout=2,
    )



def _get_channel() -> Tuple["pika.BlockingConnection", "pika.adapters.blocking_connection.BlockingChannel"]:
    connection = pika.BlockingConnection(_conn_params())
    channel = connection.channel()
    return connection, channel


# -----------------------------------------------------------------------------
# Publish: image resize (non-blocking + swallow exceptions)
# -----------------------------------------------------------------------------
def _do_publish_image_resize(post_id: int, image: str) -> None:
    if _disabled():
        return

    try:
        connection, channel = _get_channel()
        try:
            channel.queue_declare(queue=IMAGE_RESIZE_QUEUE, durable=True)
            body = json.dumps({"post_id": post_id, "image": image}).encode("utf-8")
            channel.basic_publish(
                exchange="",
                routing_key=IMAGE_RESIZE_QUEUE,
                body=body,
                properties=pika.BasicProperties(delivery_mode=2),
            )
        finally:
            try:
                connection.close()
            except Exception:
                pass
    except Exception as exc:
        # In unit tests we usually disable queues => then we don't even get here.
        # In real deployments this log is useful.
        print(f"[events] publish_image_resize failed (post_id={post_id}): {exc}")


def publish_image_resize(post_id: int, image: str) -> None:
    """
    Fire-and-forget. Never block API requests.
    """
    if _disabled():
        return

    t = Thread(target=_do_publish_image_resize, args=(post_id, image), daemon=True)
    t.start()


# -----------------------------------------------------------------------------
# Publish: textgen job (synchronous, but fail fast)
# -----------------------------------------------------------------------------
def publish_textgen_job(job_id: int, prompt: str, max_new_tokens: int = 60) -> None:
    """
    Publish a textgen job to TEXTGEN_QUEUE.

    Behavior:
    - If disabled => no-op
    - Otherwise => short timeouts, raises on failure (API catches it and sets job=error)
    """
    if _disabled():
        return

    connection = None
    try:
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
    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass


# -----------------------------------------------------------------------------
# RPC: Sentiment Check (fail fast + timeout)
# -----------------------------------------------------------------------------
class SentimentRpcClient:
    def __init__(self):
        if _disabled():
            raise RuntimeError("SentimentRpcClient created while queues are disabled")

        self.connection = pika.BlockingConnection(_conn_params())
        self.channel = self.connection.channel()

        # exclusive callback queue for replies
        result = self.channel.queue_declare(queue="", exclusive=True)
        self.callback_queue = result.method.queue

        self.response: Optional[bytes] = None
        self.corr_id: Optional[str] = None

        self.channel.basic_consume(
            queue=self.callback_queue,
            on_message_callback=self.on_response,
            auto_ack=True,
        )

    def on_response(self, ch, method, props, body):
        if self.corr_id == props.correlation_id:
            self.response = body

    def call(self, text: str, timeout_seconds: float = 5.0) -> str:
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

        start = time.time()
        while self.response is None:
            self.connection.process_data_events(time_limit=1)
            if (time.time() - start) > timeout_seconds:
                raise TimeoutError("Sentiment RPC timed out (service offline?)")

        data = json.loads(self.response.decode("utf-8"))
        return data.get("sentiment", "Neutral")

    def close(self):
        try:
            self.connection.close()
        except Exception:
            pass


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

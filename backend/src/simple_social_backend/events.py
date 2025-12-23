import json
import os

try:
    import pika
except ImportError:
    pika = None


RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "test")
RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD", "test")

IMAGE_RESIZE_QUEUE = os.getenv("IMAGE_RESIZE_QUEUE", "image_resize")
TEXTGEN_QUEUE = os.getenv("TEXT_GENERATION_QUEUE", "text_generation")


def _get_channel():
    creds = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)
    params = pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=creds)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    return connection, channel


def publish_image_resize(post_id: int, image: str) -> None:
    if pika is None or os.getenv("DISABLE_QUEUE", "").lower() == "true":
        return

    connection, channel = _get_channel()
    channel.queue_declare(queue=IMAGE_RESIZE_QUEUE, durable=True)

    body = json.dumps({"post_id": post_id, "image": image})
    channel.basic_publish(
        exchange="",
        routing_key=IMAGE_RESIZE_QUEUE,
        body=body.encode("utf-8"),
        properties=pika.BasicProperties(delivery_mode=2),
    )
    connection.close()


def publish_textgen_job(job_id: int, prompt: str, max_new_tokens: int = 60) -> None:
    """
    Pre-Post Kommentarvorschlag (TextGenJob).
    """
    if pika is None or os.getenv("DISABLE_QUEUE", "").lower() == "true":
        return

    connection, channel = _get_channel()
    channel.queue_declare(queue=TEXTGEN_QUEUE, durable=True)

    body = json.dumps({
        "type": "job",
        "job_id": job_id,
        "prompt": prompt,
        "max_new_tokens": max_new_tokens,
    })
    channel.basic_publish(
        exchange="",
        routing_key=TEXTGEN_QUEUE,
        body=body.encode("utf-8"),
        properties=pika.BasicProperties(delivery_mode=2),
    )
    connection.close()

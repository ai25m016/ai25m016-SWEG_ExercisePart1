import json
import os

try:
    import pika
except ImportError:
    pika = None  # Fallback für lokale Tests ohne Queue


QUEUE_NAME = os.getenv("IMAGE_RESIZE_QUEUE", "image_resize")
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")


def publish_image_resize(post_id: int, image: str) -> None:
    """
    Schickt eine Nachricht in die Queue, dass das Bild von Post `post_id`
    verkleinert werden soll.
    """

    # In Tests / lokal ohne RabbitMQ einfach nichts tun
    if pika is None or os.getenv("DISABLE_QUEUE", "").lower() == "true":
        return

    params = pika.ConnectionParameters(host=RABBITMQ_HOST)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()

    channel.queue_declare(queue=QUEUE_NAME, durable=True)

    body = json.dumps({"post_id": post_id, "image": image})
    channel.basic_publish(
        exchange="",
        routing_key=QUEUE_NAME,
        body=body.encode("utf-8"),
        properties=pika.BasicProperties(delivery_mode=2),
    )

    connection.close()

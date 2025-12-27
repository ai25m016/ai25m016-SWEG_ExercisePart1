from __future__ import annotations

import json
import os
import time

import pika

from .model import load_runtime, predict


RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RPC_QUEUE = os.getenv("SENTIMENT_RPC_QUEUE", "sentiment_rpc_queue")


def connect_rabbitmq():
    creds = pika.PlainCredentials(
        os.getenv("RABBITMQ_USER", "test"),
        os.getenv("RABBITMQ_PASSWORD", "test"),
    )
    while True:
        try:
            return pika.BlockingConnection(
                pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=creds, heartbeat=600)
            )
        except Exception:
            time.sleep(2)


def main() -> int:
    runtime = load_runtime()

    connection = connect_rabbitmq()
    channel = connection.channel()
    channel.queue_declare(queue=RPC_QUEUE, durable=True)

    def on_request(ch, method, props, body):
        try:
            msg = json.loads(body)
            text = msg.get("text", "")

            sentiment = predict(runtime, text)
            response = json.dumps({"sentiment": sentiment})

            ch.basic_publish(
                exchange="",
                routing_key=props.reply_to,
                properties=pika.BasicProperties(correlation_id=props.correlation_id),
                body=response,
            )
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as e:
            print(f"Error: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag)

    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=RPC_QUEUE, on_message_callback=on_request)

    print("🐰 Sentiment RPC Service Ready...")
    channel.start_consuming()
    return 0
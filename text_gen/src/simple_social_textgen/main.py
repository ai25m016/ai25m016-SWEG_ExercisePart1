import os, json, random, time
import requests
import pika

BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000")
QUEUE = os.getenv("TEXT_GENERATION_QUEUE", "text_generation")

def german_comment(prompt: str) -> str:
    p = prompt.strip()
    starters = [
        "Spannend!",
        "Klingt interessant!",
        "Oh wow!",
        "Danke fürs Teilen!",
        "Nice!",
    ]
    questions = [
        "Kannst du mehr Details geben?",
        "Wie kam es dazu?",
        "Was ist der Kontext?",
        "Was meinst du genau damit?",
        "Was ist dein Fazit?",
    ]
    templates = [
        f"{random.choice(starters)} {p} 😊 {random.choice(questions)}",
        f"{p} — {random.choice(questions)}",
        f"Zu „{p}“: {random.choice(questions)}",
        f"{random.choice(starters)} Dazu hätte ich eine Frage: {random.choice(questions)}",
    ]
    return random.choice(templates)

def handle_message(body: bytes):
    msg = json.loads(body.decode("utf-8"))

    # NEU: pre-post job (job_id)
    if msg.get("type") == "job" and "job_id" in msg:
        job_id = msg["job_id"]
        prompt = msg.get("prompt", "")
        text = german_comment(prompt)

        requests.put(
            f"{BACKEND_URL}/textgen/jobs/{job_id}",
            json={"status": "done", "generated_text": text, "error": None},
            timeout=10,
        )
        return

    # ALT: post_id (falls du es noch drin hast)
    # -> kannst du optional weiter unterstützen oder ignorieren.

def main():
    host = os.getenv("RABBITMQ_HOST", "rabbitmq")
    user = os.getenv("RABBITMQ_USER", "test")
    pw = os.getenv("RABBITMQ_PASSWORD", "test")

    creds = pika.PlainCredentials(user, pw)
    params = pika.ConnectionParameters(host=host, credentials=creds)

    while True:
        try:
            connection = pika.BlockingConnection(params)
            channel = connection.channel()
            channel.queue_declare(queue=QUEUE, durable=True)

            def callback(ch, method, properties, body):
                try:
                    handle_message(body)
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                except Exception as e:
                    print("TextGen error:", e)
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue=QUEUE, on_message_callback=callback)
            channel.start_consuming()
        except Exception as e:
            print("RabbitMQ connect error:", e)
            time.sleep(2)

if __name__ == "__main__":
    main()

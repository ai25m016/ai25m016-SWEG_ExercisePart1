import os
import time
import json
from pathlib import Path

import pika
import requests
from PIL import Image

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())  # findet .env automatisch (auch Repo-Root)

# RabbitMQ / Backend / Bilder-Verzeichnis
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
QUEUE_NAME = os.getenv("IMAGE_RESIZE_QUEUE", "image_resize")
BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL", "http://backend:8000")
IMAGES_DIR = os.getenv("IMAGES_DIR", "/app/backend/images")

images_path = Path(IMAGES_DIR)
if not images_path.is_absolute():
    # Wenn relativ: relativ zum Repo-Root finden und dann zu backend/ auflösen
    repo_root = Path(find_dotenv()).resolve().parent
    # Wenn du IMAGES_DIR=images meinst: das ist backend/images
    images_path = (repo_root / "backend" / IMAGES_DIR).resolve()

IMAGES_DIR = str(images_path)

# Größe des Thumbnails (kannst du anpassen)
THUMB_SIZE = (256, 256)


def url_to_fs_path(image_url: str) -> Path:
    """
    Wandelt eine URL wie /images/original/foo.png
    in einen Dateipfad unterhalb von IMAGES_DIR um.
    """
    if image_url.startswith("/images/"):
        rel = image_url[len("/images/") :]  # "original/foo.png"
    else:
        rel = image_url.lstrip("/")
    return Path(IMAGES_DIR) / rel


def make_thumb_paths(image_url: str):
    """
    Aus /images/original/foo.png wird:
      - fs_original:  IMAGES_DIR / original / foo.png
      - fs_thumb:     IMAGES_DIR / thumbs  / foo.png
      - url_thumb:   /images/thumbs/foo.png
    """
    if image_url.startswith("/images/"):
        rel = image_url[len("/images/") :]
    else:
        rel = image_url.lstrip("/")

    # original/ → thumbs/
    rel_thumb = rel.replace("original/", "thumbs/", 1)
    if rel_thumb == rel:
        # falls "original/" nicht drin ist, fallback
        rel_thumb = "thumbs/" + os.path.basename(rel)

    fs_original = Path(IMAGES_DIR) / rel
    fs_thumb = Path(IMAGES_DIR) / rel_thumb
    url_thumb = "/images/" + rel_thumb.replace("\\", "/")

    return fs_original, fs_thumb, url_thumb

def connect_rabbitmq():
    params = pika.ConnectionParameters(
        host=RABBITMQ_HOST,
        heartbeat=60,
        blocked_connection_timeout=30,
        connection_attempts=1,   # wir machen die Retries selbst
        retry_delay=0,
    )

    for attempt in range(1, 31):  # ~30 Versuche
        try:
            print(f"⏳ RabbitMQ connect Versuch {attempt}/30 ...")
            return pika.BlockingConnection(params)
        except Exception as e:
            print(f"RabbitMQ noch nicht bereit: {e}")
            time.sleep(1.0)

    raise RuntimeError("RabbitMQ nicht erreichbar nach 30s")

def main():
    print("Image-Resizer startet...")
    print(f"Verbinde zu RabbitMQ auf {RABBITMQ_HOST}, Queue: {QUEUE_NAME}")
    print(f"IMAGES_DIR = {IMAGES_DIR}")

    params = pika.ConnectionParameters(host=RABBITMQ_HOST)
    connection = connect_rabbitmq()
    channel = connection.channel()
    channel.queue_declare(queue=QUEUE_NAME, durable=True)

    def callback(ch, method, properties, body):
        try:
            msg = json.loads(body.decode("utf-8"))
            post_id = msg["post_id"]
            image_url = msg["image"]

            print(f"📩 Aufgabe erhalten: post_id={post_id}, image={image_url}")

            fs_original, fs_thumb, thumb_url = make_thumb_paths(image_url)
            print(f"🖼 Original-Datei: {fs_original}")
            print(f"🖼 Thumbnail-Datei: {fs_thumb}")
            print(f"🖼 Thumbnail-URL: {thumb_url}")

            if not fs_original.exists():
                raise FileNotFoundError(f"Originalbild nicht gefunden: {fs_original}")

            # Zielverzeichnis für Thumbnail anlegen
            fs_thumb.parent.mkdir(parents=True, exist_ok=True)

            # Bild laden & verkleinern
            with Image.open(fs_original) as im:
                im.thumbnail(THUMB_SIZE)  # behält Seitenverhältnis
                im.save(fs_thumb)
            print("✅ Thumbnail erzeugt und gespeichert.")

            # Backend informieren (PUT /posts/{id}/thumbnail)
            url = f"{BACKEND_BASE_URL}/posts/{post_id}/thumbnail"
            payload = {"image_small": thumb_url}
            print(f"➡️  Sende Thumbnail-Update an {url}: {payload}")
            resp = requests.put(url, json=payload, timeout=5)
            # Nur bei erfolgreichem HTTP-Status ack'en
            try:
                resp.raise_for_status()
            except requests.HTTPError as http_exc:
                print(f"⬅️  Backend-Fehler: {resp.status_code} {resp.text}")
                raise http_exc

            print(f"⬅️  Antwort Backend: {resp.status_code} {resp.text}")
            ch.basic_ack(delivery_tag=method.delivery_tag)

        except Exception as exc:
            print(f"❌ Fehler bei Verarbeitung der Nachricht: {exc}")
            # Wichtig: Ohne ACK/NACK bleibt die Message unacked und blockiert bei prefetch_count=1.
            # FileNotFound ist i.d.R. nicht transient → nicht requeue'n.
            requeue = not isinstance(exc, FileNotFoundError)
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=requeue)

    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=QUEUE_NAME, on_message_callback=callback)

    print("⏳ Warte auf Nachrichten...")
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        print("Beende...")
    finally:
        connection.close()


if __name__ == "__main__":
    # kleines Delay, damit RabbitMQ & Backend hochfahren
    time.sleep(5)
    main()

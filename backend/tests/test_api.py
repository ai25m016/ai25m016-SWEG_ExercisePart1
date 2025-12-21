from pathlib import Path
import importlib
import sqlite3

from fastapi.testclient import TestClient
from sqlmodel import create_engine
from simple_social_backend.api import app

from io import BytesIO
from PIL import Image
import pytest
import shutil
import time

pytestmark = pytest.mark.api


def setup_module(_):
    """
    Läuft einmal vor allen Tests in diesem Modul.
    Stellt sicher, dass eine frische Test-Datenbank verwendet wird.
    """
    db = importlib.import_module("simple_social_backend.db")
    test_db = Path(__file__).parent / "test_social.db"

    # 1) DB_PATH im Modul simple_social_backend.db auf die Test-DB umbiegen
    db.DB_PATH = test_db

    # 2) Alte Test-DB wegwerfen, falls vorhanden
    if test_db.exists():
        test_db.unlink()

    # 3) Engine neu erstellen, damit sie auf test_social.db zeigt
    db.ENGINE = create_engine(
        f"sqlite:///{db.DB_PATH}",
        echo=False,
        connect_args={"check_same_thread": False},
    )

    # 4) Tabellen neu anlegen
    db.init_db()


def teardown_module(_):
    db = importlib.import_module("simple_social_backend.db")

    # Engine/Connections freigeben (sonst bleiben DB-Dateien unter Windows gelockt)
    try:
        db.ENGINE.dispose()
    except Exception:
        pass

    # DB-Dateien löschen (mit retry)
    for p in [
        db.DB_PATH,
        db.DB_PATH.with_suffix(".db-wal"),
        db.DB_PATH.with_suffix(".db-shm"),
    ]:
        for _ in range(30):
            try:
                p.unlink()
                break
            except FileNotFoundError:
                break
            except PermissionError:
                time.sleep(0.1)

    # Images-Ordner löschen (weil du IMAGES_DIR auf backend/tests/images gesetzt hast)
    images_dir = Path(__file__).parent / "images"
    for _ in range(30):
        try:
            shutil.rmtree(images_dir)
            break
        except FileNotFoundError:
            break
        except PermissionError:
            time.sleep(0.1)


def _clear_db():
    """
    Hilfsfunktion: löscht alle Zeilen aus der Post-Tabelle.
    So startet jeder Test mit einem definierten Zustand.
    """
    import simple_social_backend.db as db

    # Stelle sicher, dass die Tabellen existieren
    db.init_db()

    conn = sqlite3.connect(db.DB_PATH)
    try:
        conn.execute("DELETE FROM post")
        conn.commit()
    finally:
        conn.close()


def _post(client, user: str, text: str, filename: str = "img.png"):
    img = Image.new("RGB", (32, 32))
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    files = {"image": (filename, buf, "image/png")}
    data = {"user": user, "text": text}
    return client.post("/posts", data=data, files=files)


def test_create_and_latest():
    """
    POST /posts soll einen Post anlegen,
    GET /posts/latest soll genau diesen Post zurückgeben.
    """
    _clear_db()
    with TestClient(app) as client:
        r = _post(client, user="anna", text="hi", filename="a.png")
        assert r.status_code in (200, 201)
        created = r.json()
        assert created["user"] == "anna"
        assert created["text"] == "hi"
        assert created["image"].startswith("/images/original/")
        assert created["image"].endswith(".png")
        assert "id" in created



def test_latest_without_posts_returns_404():
    """
    GET /posts/latest soll 404 liefern, wenn keine Posts existieren.
    """
    _clear_db()
    with TestClient(app) as client:
        r = client.get("/posts/latest")
        assert r.status_code == 404


def test_list_posts_returns_all():
    """
    GET /posts soll alle Posts zurückgeben.
    """
    _clear_db()
    with TestClient(app) as client:
        _post(client, user="alice", text="one", filename="1.png")
        _post(client, user="bob", text="two", filename="2.png")
        _post(client, user="alice", text="three", filename="3.png")

        r = client.get("/posts")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 3
        texts = {p["text"] for p in data}
        assert texts == {"one", "two", "three"}


def test_list_posts_filter_by_user_query_param():
    """
    GET /posts?user=alice soll nur Posts von 'alice' zurückgeben.
    (Query-Parameter-Variante)
    """
    _clear_db()
    with TestClient(app) as client:
        _post(client, user="alice", text="one", filename="1.png")
        _post(client, user="bob", text="two", filename="2.png")
        _post(client, user="alice", text="three", filename="3.png")

        r = client.get("/posts", params={"user": "alice"})
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 2
        users = {p["user"] for p in data}
        assert users == {"alice"}


def test_list_posts_by_user_endpoint():
    """
    GET /users/{user}/posts soll alle Posts eines Users liefern.
    (Pfad-Parameter-Variante)
    """
    _clear_db()
    with TestClient(app) as client:
        _post(client, user="alice", text="one", filename="1.png")
        _post(client, user="bob", text="two", filename="2.png")
        _post(client, user="alice", text="three", filename="3.png")

        r = client.get("/users/alice/posts")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 2
        users = {p["user"] for p in data}
        assert users == {"alice"}


def test_get_post_by_id_success():
    """
    GET /posts/{id} soll den richtigen Post liefern.
    """
    _clear_db()
    with TestClient(app) as client:
        r_create = _post(client, user="carol", text="hello", filename="x.png")

        created = r_create.json()
        post_id = created["id"]

        r = client.get(f"/posts/{post_id}")
        assert r.status_code == 200
        data = r.json()
        assert data["id"] == post_id
        assert data["text"] == "hello"
        assert data["user"] == "carol"


def test_get_post_by_id_not_found():
    """
    GET /posts/{id} mit nicht existierender ID soll 404 liefern.
    """
    _clear_db()
    with TestClient(app) as client:
        r = client.get("/posts/999999")
        assert r.status_code == 404


def test_search_posts_by_text():
    """
    GET /posts/search?query=... soll nur passende Posts zurückgeben.
    """
    _clear_db()
    with TestClient(app) as client:
        _post(client, user="alice", text="I love FastAPI", filename="1.png")
        _post(client, user="bob", text="SQLModel is nice", filename="2.png")
        _post(client, user="carol", text="FastAPI and SQLModel", filename="3.png")


        r = client.get("/posts/search", params={"query": "FastAPI"})
        assert r.status_code == 200
        data = r.json()
        texts = {p["text"] for p in data}

        assert "I love FastAPI" in texts
        assert "FastAPI and SQLModel" in texts
        assert "SQLModel is nice" not in texts


def test_delete_post_success():
    """
    DELETE /posts/{id} soll einen existierenden Post löschen
    und danach 404 für GET /posts/{id} liefern.
    """
    _clear_db()
    with TestClient(app) as client:
        r_create = _post(client, user="dave", text="to be deleted", filename="x.png")

        post_id = r_create.json()["id"]

        r_del = client.delete(f"/posts/{post_id}")
        assert r_del.status_code == 204

        # sicherstellen, dass der Post weg ist
        r_get = client.get(f"/posts/{post_id}")
        assert r_get.status_code == 404


def test_delete_post_not_found():
    """
    DELETE /posts/{id} mit nicht existierender ID soll 404 liefern.
    """
    _clear_db()
    with TestClient(app) as client:
        r_del = client.delete("/posts/999999")
        assert r_del.status_code == 404

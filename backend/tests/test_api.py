from pathlib import Path
import importlib
import sqlite3

from fastapi.testclient import TestClient

from simple_social_backend.api import app


def setup_module(_):
    """
    Läuft einmal vor allen Tests in diesem Modul.
    Stellt sicher, dass eine frische Test-Datenbank verwendet wird.
    """
    db = importlib.import_module("simple_social_backend.db")
    test_db = Path(__file__).parent / "test_social.db"

    # DB_PATH im Modul simple_social_backend.db auf die Test-DB umbiegen
    db.DB_PATH = test_db

    # Alte Test-DB wegwerfen, falls vorhanden
    if test_db.exists():
        test_db.unlink()

    # Tabellen neu anlegen
    db.init_db()


def teardown_module(_):
    """
    Läuft einmal nach allen Tests.
    Löscht die Test-Datenbank und zugehörige WAL/SHM-Dateien.
    """
    db = importlib.import_module("simple_social_backend.db")
    try:
        sqlite3.connect(db.DB_PATH).close()
    except Exception:
        pass

    for p in [
        db.DB_PATH,
        db.DB_PATH.with_suffix(".db-wal"),
        db.DB_PATH.with_suffix(".db-shm"),
    ]:
        try:
            p.unlink()
        except Exception:
            pass


def _clear_db():
    """
    Hilfsfunktion: löscht alle Zeilen aus der Post-Tabelle.
    So startet jeder Test mit einem definierten Zustand.
    """
    db = importlib.import_module("simple_social_backend.db")
    conn = sqlite3.connect(db.DB_PATH)
    try:
        conn.execute("DELETE FROM post")
        conn.commit()
    finally:
        conn.close()


def test_create_and_latest():
    """
    POST /posts soll einen Post anlegen,
    GET /posts/latest soll genau diesen Post zurückgeben.
    """
    _clear_db()
    with TestClient(app) as client:
        r = client.post(
            "/posts",
            json={"image": "a.png", "text": "hi", "user": "anna"},
        )
        assert r.status_code in (200, 201)
        created = r.json()
        assert created["user"] == "anna"
        assert created["image"] == "a.png"
        assert "id" in created
        assert created["id"] is not None

        r = client.get("/posts/latest")
        assert r.status_code == 200
        data = r.json()
        assert data["id"] == created["id"]
        assert data["text"] == "hi"


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
        client.post("/posts", json={"image": "1.png", "text": "one", "user": "alice"})
        client.post("/posts", json={"image": "2.png", "text": "two", "user": "bob"})
        client.post("/posts", json={"image": "3.png", "text": "three", "user": "alice"})

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
        client.post("/posts", json={"image": "1.png", "text": "one", "user": "alice"})
        client.post("/posts", json={"image": "2.png", "text": "two", "user": "bob"})
        client.post("/posts", json={"image": "3.png", "text": "three", "user": "alice"})

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
        client.post("/posts", json={"image": "1.png", "text": "one", "user": "alice"})
        client.post("/posts", json={"image": "2.png", "text": "two", "user": "bob"})
        client.post("/posts", json={"image": "3.png", "text": "three", "user": "alice"})

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
        r_create = client.post(
            "/posts",
            json={"image": "x.png", "text": "hello", "user": "carol"},
        )
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
        client.post(
            "/posts",
            json={"image": "1.png", "text": "I love FastAPI", "user": "alice"},
        )
        client.post(
            "/posts",
            json={"image": "2.png", "text": "SQLModel is nice", "user": "bob"},
        )
        client.post(
            "/posts",
            json={"image": "3.png", "text": "FastAPI and SQLModel", "user": "carol"},
        )

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
        r_create = client.post(
            "/posts",
            json={"image": "x.png", "text": "to be deleted", "user": "dave"},
        )
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

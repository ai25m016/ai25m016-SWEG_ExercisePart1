import os
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlmodel import Session, create_engine, delete

from simple_social_backend.api import app
from simple_social_backend.models import Post, TextGenJob
import simple_social_backend.db as db

pytestmark = pytest.mark.api


@pytest.fixture(scope="module", autouse=True)
def _use_postgres(docker_postgres):
    """
    Wird erst ausgeführt, NACHDEM docker_postgres bereit ist.
    """
    # Kein SQLite mehr
    os.environ.pop("DB_PATH", None)

    # Optional: damit API-Tests keine RabbitMQ brauchen
    # (falls euer Code das respektiert)
    os.environ["DISABLE_QUEUE"] = "true"
    # Falls es so etwas bei euch gibt:
    # os.environ["DISABLE_SENTIMENT"] = "true"

    db_name = docker_postgres["db_name"]
    db_user = docker_postgres["db_user"]
    db_pw = docker_postgres["db_password"]

    dsn = f"postgresql+psycopg://{db_user}:{db_pw}@127.0.0.1:5432/{db_name}"
    os.environ["DATABASE_URL_LOCAL"] = dsn

    db.ENGINE = create_engine(dsn, echo=False, pool_pre_ping=True)
    db.init_db()

    yield

    try:
        db.ENGINE.dispose()
    except Exception:
        pass


def _clear_db():
    db.init_db()
    with Session(db.get_engine()) as session:
        session.exec(delete(Post))
        session.exec(delete(TextGenJob))
        session.commit()


def _post(client, user: str, text: str, filename: str = "img.png"):
    img = Image.new("RGB", (32, 32))
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    files = {"image": (filename, buf, "image/png")}
    data = {"user": user, "text": text}
    return client.post("/posts", data=data, files=files)


def test_latest_without_posts_returns_404():
    _clear_db()
    with TestClient(app) as client:
        r = client.get("/posts/latest")
        assert r.status_code == 404


def test_create_and_latest():
    _clear_db()
    with TestClient(app) as client:
        r = _post(client, user="anna", text="hi", filename="a.png")
        assert r.status_code in (200, 201)

        r2 = client.get("/posts/latest")
        assert r2.status_code == 200
        latest = r2.json()
        assert latest["user"] == "anna"
        assert latest["text"] == "hi"


def test_list_posts_returns_all():
    _clear_db()
    with TestClient(app) as client:
        _post(client, user="alice", text="one", filename="1.png")
        _post(client, user="bob", text="two", filename="2.png")
        _post(client, user="alice", text="three", filename="3.png")

        r = client.get("/posts")
        assert r.status_code == 200
        assert len(r.json()) == 3


def test_list_posts_filter_by_user_query_param():
    _clear_db()
    with TestClient(app) as client:
        _post(client, user="alice", text="one", filename="1.png")
        _post(client, user="bob", text="two", filename="2.png")
        _post(client, user="alice", text="three", filename="3.png")

        r = client.get("/posts", params={"user": "alice"})
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 2
        assert {p["user"] for p in data} == {"alice"}

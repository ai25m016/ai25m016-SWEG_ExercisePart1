from io import BytesIO

import pytest
from PIL import Image
from sqlmodel import Session, delete

from simple_social_backend.models import Post, TextGenJob
import simple_social_backend.db as db

pytestmark = pytest.mark.api


def _clear_db():
    # Tabellen sicher vorhanden
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


def test_latest_without_posts_returns_404(client):
    _clear_db()
    r = client.get("/posts/latest")
    assert r.status_code == 404


def test_create_and_latest(client):
    _clear_db()
    r = _post(client, user="anna", text="hi", filename="a.png")
    assert r.status_code in (200, 201)

    r2 = client.get("/posts/latest")
    assert r2.status_code == 200
    latest = r2.json()
    assert latest["user"] == "anna"
    assert latest["text"] == "hi"


def test_list_posts_returns_all(client):
    _clear_db()
    _post(client, user="alice", text="one", filename="1.png")
    _post(client, user="bob", text="two", filename="2.png")
    _post(client, user="alice", text="three", filename="3.png")

    r = client.get("/posts")
    assert r.status_code == 200
    assert len(r.json()) == 3


def test_list_posts_filter_by_user_query_param(client):
    _clear_db()
    _post(client, user="alice", text="one", filename="1.png")
    _post(client, user="bob", text="two", filename="2.png")
    _post(client, user="alice", text="three", filename="3.png")

    r = client.get("/posts", params={"user": "alice"})
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    assert {p["user"] for p in data} == {"alice"}

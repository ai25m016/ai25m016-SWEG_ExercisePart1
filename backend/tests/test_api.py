from pathlib import Path
import importlib, sqlite3
from fastapi.testclient import TestClient
from simple_social_backend.api import app

def setup_module(_):
    db = importlib.import_module("simple_social_backend.db")
    test_db = Path(__file__).parent / "test_social.db"
    db.DB_PATH = test_db
    if test_db.exists(): test_db.unlink()
    db.init_db()

def teardown_module(_):
    db = importlib.import_module("simple_social_backend.db")
    try: sqlite3.connect(db.DB_PATH).close()
    except Exception: pass
    for p in [db.DB_PATH, db.DB_PATH.with_suffix(".db-wal"), db.DB_PATH.with_suffix(".db-shm")]:
        try: p.unlink()
        except Exception: pass

def test_create_and_latest():
    with TestClient(app) as client:
        r = client.post("/posts", json={"image":"a.png","text":"hi","user":"anna"})
        assert r.status_code in (200, 201)  # 201 wenn du es so dekorierst
        r = client.get("/posts/latest")
        assert r.status_code == 200
        data = r.json()
        assert data["user"] == "anna"
        assert data["image"] == "a.png"

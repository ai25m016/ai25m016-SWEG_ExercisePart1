import os
import time
import subprocess
from io import BytesIO

import pytest
import requests
from PIL import Image

pytestmark = pytest.mark.persistence

BASE = os.getenv("PERSIST_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
COMPOSE_FILE = os.getenv("PERSIST_COMPOSE_FILE", "docker-compose.local.yml")

def run(*args):
    subprocess.check_call(args)

def wait_backend(timeout_s=80):
    end = time.time() + timeout_s
    last = None
    while time.time() < end:
        try:
            r = requests.get(f"{BASE}/docs", timeout=2)
            if r.status_code == 200:
                return
            last = f"{r.status_code}"
        except Exception as e:
            last = repr(e)
        time.sleep(2)
    raise RuntimeError(f"Backend not ready in time (last={last})")

def create_post(marker: str):
    img = Image.new("RGB", (32, 32))
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    files = {"image": ("persist.png", buf, "image/png")}
    data = {"user": "persist_user", "text": marker}

    r = requests.post(f"{BASE}/posts", data=data, files=files, timeout=20)
    r.raise_for_status()
    return r.json()

def post_exists(marker: str) -> bool:
    r = requests.get(f"{BASE}/posts", timeout=10)
    r.raise_for_status()
    posts = r.json()
    return any(p.get("text") == marker for p in posts)

@pytest.fixture
def compose_stack():
    # erst mal "clean", damit ein alter Stack nicht reinfunkt
    run("docker", "compose", "-f", COMPOSE_FILE, "down", "-v")

    # Stack hoch
    run("docker", "compose", "-f", COMPOSE_FILE, "up", "-d", "--build", "db", "backend")
    wait_backend(timeout_s=120)

    yield

    # am Ende immer aufräumen
    run("docker", "compose", "-f", COMPOSE_FILE, "down", "-v")

def test_db_persistence_survives_restart(compose_stack):
    marker = f"persist-test-{int(time.time())}"

    create_post(marker)

    # down ohne -v => Volume bleibt
    run("docker", "compose", "-f", COMPOSE_FILE, "down")

    # wieder hoch
    run("docker", "compose", "-f", COMPOSE_FILE, "up", "-d", "db", "backend")
    wait_backend(timeout_s=120)

    assert post_exists(marker), f"Post '{marker}' not found after restart"

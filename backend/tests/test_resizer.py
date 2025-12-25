# backend/tests/test_resizer.py
import os
import time
from io import BytesIO

import pytest
import requests
from PIL import Image

pytestmark = pytest.mark.resizer

BASE = os.getenv("E2E_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


def test_resizer_generates_thumbnail():
    # Stack wird durch conftest.py (autouse) gestartet/gestoppt.
    img = Image.new("RGB", (640, 480))
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    files = {"image": ("ci.png", buf, "image/png")}
    data = {"user": "ci", "text": "e2e"}

    r = requests.post(f"{BASE}/posts", data=data, files=files, timeout=60)
    r.raise_for_status()
    post_id = int(r.json()["id"])

    deadline = time.time() + 180
    thumb_url = None

    while time.time() < deadline:
        rr = requests.get(f"{BASE}/posts/{post_id}", timeout=5)
        if rr.status_code == 200:
            p = rr.json()
            thumb_url = p.get("image_small")
            if thumb_url:
                chk = requests.get(f"{BASE}{thumb_url}", timeout=10)
                if chk.status_code == 200 and chk.headers.get("content-type", "").startswith("image/"):
                    im = Image.open(BytesIO(chk.content))
                    assert im.size[0] <= 256 and im.size[1] <= 256
                    return
        time.sleep(0.5)

    raise AssertionError(f"Thumbnail nicht erzeugt für post_id={post_id}, last thumb={thumb_url}")

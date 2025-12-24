import os
import time
from io import BytesIO

import pytest
import requests
from PIL import Image


@pytest.mark.e2e
def test_resizer_generates_thumbnail(backend_server, resizer_process):
    base = backend_server["base"]

    img = Image.new("RGB", (640, 480))
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    files = {"image": ("ci.png", buf, "image/png")}
    data = {"user": "ci", "text": "e2e"}
    r = requests.post(f"{base}/posts", data=data, files=files, timeout=60)
    r.raise_for_status()
    post_id = int(r.json()["id"])

    deadline = time.time() + 120
    thumb_url = None

    while time.time() < deadline:
        rr = requests.get(f"{base}/posts/{post_id}", timeout=5)
        if rr.status_code == 200:
            p = rr.json()
            thumb_url = p.get("image_small")
            if thumb_url:
                chk = requests.get(f"{base}{thumb_url}", timeout=5)
                if chk.status_code == 200 and chk.headers.get("content-type", "").startswith("image/"):
                    return
        time.sleep(0.5)

    raise AssertionError(f"Thumbnail nicht erzeugt für post_id={post_id}, last thumb={thumb_url}")

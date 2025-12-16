import os
import time
from io import BytesIO

import pytest
import requests
from PIL import Image


@pytest.mark.e2e
def test_resizer_generates_thumbnail(backend_server, resizer_process):
    base = backend_server["base"]

    # 1) Bild on-the-fly erzeugen (kein Repo-Testbild nötig)
    img = Image.new("RGB", (640, 480))
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    # 2) Post erstellen (multipart)
    files = {"image": ("ci.png", buf, "image/png")}
    data = {"user": "ci", "text": "e2e"}
    r = requests.post(f"{base}/posts", data=data, files=files, timeout=20)
    r.raise_for_status()
    post = r.json()
    post_id = int(post["id"])

    # 3) Warten bis image_small gesetzt + Thumbnail via HTTP abrufbar ist
    deadline = time.time() + 30
    thumb_url = None

    while time.time() < deadline:
        rr = requests.get(f"{base}/posts", timeout=5)
        rr.raise_for_status()
        posts = rr.json()
        p = next((x for x in posts if int(x.get("id", -1)) == post_id), None)
        if p and p.get("image_small"):
            thumb_url = p["image_small"]
            chk = requests.get(f"{base}{thumb_url}", timeout=5)
            if chk.status_code == 200 and chk.headers.get("content-type", "").startswith("image/"):
                return
        time.sleep(1)

    raise AssertionError(f"Thumbnail nicht erzeugt für post_id={post_id}, last thumb={thumb_url}")

import os
import sys
import time
import base64
from pathlib import Path

import requests


BASE = os.getenv("BACKEND_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
IMAGES_DIR = os.getenv("IMAGES_DIR", os.path.join("backend", "images"))
CHECK_FS = os.getenv("CHECK_FS", "1") == "1"   # lokal 1, im Docker/CI 0
TIMEOUT_S = int(os.getenv("RESIZER_TIMEOUT", "40"))

# 1x1 PNG (transparent) – damit der Test IMMER ein Bild hat
_PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGMAAQAABQABDQottAAAAABJRU5ErkJggg=="
)


def wait_for_backend(timeout_s: int = 30) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            r = requests.get(f"{BASE}/posts", timeout=2)
            if r.status_code in (200, 404):  # 404 wäre komisch, aber "Server lebt"
                return
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError(f"Backend nicht erreichbar unter {BASE} (Timeout {timeout_s}s)")


def ensure_test_image() -> Path:
    orig = Path(IMAGES_DIR) / "original"
    orig.mkdir(parents=True, exist_ok=True)
    p = orig / "ci.png"
    if not p.exists():
        p.write_bytes(_PNG_1X1)
    return p


def create_post(img_path: Path) -> dict:
    with img_path.open("rb") as f:
        files = {"image": (img_path.name, f, "application/octet-stream")}
        data = {"user": "ci", "text": "ci smoke"}
        r = requests.post(f"{BASE}/posts", data=data, files=files, timeout=20)
    r.raise_for_status()
    return r.json()


def wait_for_thumbnail(post_id: int, timeout_s: int = 40):
    deadline = time.time() + timeout_s

    while time.time() < deadline:
        r = requests.get(f"{BASE}/posts", timeout=5)
        r.raise_for_status()
        posts = r.json()

        post = next((p for p in posts if int(p.get("id", -1)) == post_id), None)
        if post and post.get("image_small"):
            thumb_url = post["image_small"]  # /images/thumbs/...
            fname = thumb_url.split("/")[-1]

            # 1) Lokal: Dateisystem prüfen
            if CHECK_FS:
                thumb_path = Path(IMAGES_DIR) / "thumbs" / fname
                if thumb_path.exists():
                    return post, str(thumb_path)

            # 2) Docker/CI: per HTTP prüfen
            rr = requests.get(f"{BASE}{thumb_url}", timeout=5)
            ctype = rr.headers.get("content-type", "")
            if rr.status_code == 200 and ctype.startswith("image/"):
                return post, f"{BASE}{thumb_url}"

        time.sleep(1)

    raise RuntimeError("Thumbnail wurde nicht rechtzeitig erzeugt / image_small nicht gesetzt")


def main() -> int:
    print(f"BASE={BASE}")
    print(f"IMAGES_DIR={IMAGES_DIR}")
    print(f"CHECK_FS={CHECK_FS}")

    wait_for_backend(timeout_s=30)

    img_path = ensure_test_image()
    print("Using test image:", img_path)

    post = create_post(img_path)
    post_id = int(post["id"])
    print(f"Created post id: {post_id} image: {post.get('image')}")

    post2, thumb_ref = wait_for_thumbnail(post_id, timeout_s=TIMEOUT_S)
    print("OK:", post2["image_small"], "->", thumb_ref)
    print("✅ PASS resizer-smoke")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print("❌ FAIL resizer-smoke:", e)
        raise SystemExit(1)

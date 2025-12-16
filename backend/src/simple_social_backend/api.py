from contextlib import asynccontextmanager
from datetime import datetime
from typing import List

import os
from pathlib import Path

from dotenv import load_dotenv, find_dotenv

# Lädt automatisch die Repo-Root .env (ohne dass du --env-file oder $env:... setzen musst)
# Überschreibt vorhandene Environment-Variablen NICHT (override=False ist Default).
load_dotenv(find_dotenv())

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .events import publish_image_resize  # oder .eventy, wenn du den Namen nicht änderst
from .db import (
    init_db,
    add_post,
    get_latest_post,
    get_all_posts,
    get_post_by_id,
    search_posts,
    delete_post as delete_post_from_db,
    set_post_thumbnail,
)


class PostOut(BaseModel):
    id: int
    image: str
    image_small: str | None = None
    text: str
    user: str
    created_at: datetime


class ThumbnailIn(BaseModel):
    image_small: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db()
    yield
    # Shutdown (optional)


app = FastAPI(
    title="Simple Social",
    description="Simple Social media REST API for the course exercise.",
    lifespan=lifespan,
)

# Bilder-Verzeichnis: stabil, egal ob du aus Repo-Root oder aus backend/ startest
IMAGES_DIR = Path(
    os.getenv(
        "IMAGES_DIR",
        # Default: <repo>/backend/images
        Path(__file__).resolve().parents[2] / "images",
    )
).resolve()

# Bilder statisch ausliefern (URLs bleiben /images/...
app.mount(
    "/images",
    StaticFiles(directory=str(IMAGES_DIR), check_dir=False),
    name="images",
)

origins = [
    "http://127.0.0.1:5500",
    "http://localhost:5500",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/posts", response_model=PostOut, summary="Create a new post")
async def create_post(
    image: UploadFile = File(...),
    text: str = Form(...),
    user: str = Form(...),
):
    """
    Einen neuen Post anlegen:
    - Bild-Datei speichern
    - Post in DB anlegen
    - Event in Queue legen
    """

    # Bilder-Verzeichnis anlegen (z.B. <IMAGES_DIR>/original/)
    base_dir = IMAGES_DIR / "original"
    base_dir.mkdir(parents=True, exist_ok=True)

    # Dateiname generieren (einfach, aber eindeutig genug für die Übung)
    suffix = Path(image.filename).suffix or ".jpg"
    timestamp = int(datetime.utcnow().timestamp())
    filename = f"{timestamp}_{user}{suffix}"
    file_path = base_dir / filename

    # Datei speichern
    content = await image.read()
    with open(file_path, "wb") as f:
        f.write(content)

    # URL/Pfad, den Frontend & Resizer verwenden
    image_url = f"/images/original/{filename}"

    # In DB speichern
    post_id = add_post(image=str(image_url), text=text, user=user)
    created = get_post_by_id(post_id)
    if not created:
        raise HTTPException(status_code=500, detail="Post could not be created")

    # Event für Image-Resizer verschicken (post_id + image)
    try:
        publish_image_resize(post_id, created["image"])
    except Exception as exc:  # noqa: BLE001
        print(f"Could not publish image resize event: {exc}")

    return created


@app.get("/posts/latest", response_model=PostOut, summary="Get the latest post")
def latest_post():
    post = get_latest_post()
    if not post:
        raise HTTPException(status_code=404, detail="No posts found")
    return post


@app.get("/posts", response_model=list[PostOut], summary="List posts")
def list_posts(user: str | None = None):
    return get_all_posts(user=user)


@app.get(
    "/posts/search",
    response_model=list[PostOut],
    summary="Search posts by text",
)
def search(query: str):
    return search_posts(query=query)


@app.get("/posts/{post_id}", response_model=PostOut, summary="Get post by ID")
def get_post(post_id: int):
    post = get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post


@app.put(
    "/posts/{post_id}/thumbnail",
    response_model=PostOut,
    summary="Set thumbnail image for a post",
)
def update_thumbnail(post_id: int, payload: ThumbnailIn):
    updated = set_post_thumbnail(post_id, payload.image_small)
    if not updated:
        raise HTTPException(status_code=404, detail="Post not found")
    return updated


@app.get(
    "/users/{user}/posts",
    response_model=List[PostOut],
    summary="List posts by user",
)
def list_user_posts(user: str):
    return get_all_posts(user=user)


@app.delete(
    "/posts/{post_id}",
    status_code=204,
    summary="Delete post by ID",
)
def delete_post(post_id: int):
    deleted = delete_post_from_db(post_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Post not found")
    return

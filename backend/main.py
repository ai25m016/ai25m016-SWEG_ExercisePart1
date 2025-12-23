import requests
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import List
import os
from pathlib import Path

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .events import publish_image_resize, publish_textgen_job
from .db import (
    init_db,
    add_post,
    get_latest_post,
    get_all_posts,
    get_post_by_id,
    search_posts,
    delete_post as delete_post_from_db,
    set_post_thumbnail,
    create_textgen_job,
    get_textgen_job,
    set_textgen_job_result,
)

class PostOut(BaseModel):
    id: int
    image: str
    image_small: str | None = None
    text: str
    user: str
    created_at: datetime

class TextGenSuggestRequest(BaseModel):
    prompt: str
    max_new_tokens: int = 60

class TextGenJobOut(BaseModel):
    id: int
    prompt: str
    max_new_tokens: int
    status: str
    generated_text: str | None = None
    error: str | None = None

class TextGenJobResultIn(BaseModel):
    status: str  # done | error
    generated_text: str | None = None
    error: str | None = None

class ThumbnailIn(BaseModel):
    image_small: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(
    title="Simple Social",
    description="Simple Social media REST API for the course exercise.",
    lifespan=lifespan,
)

IMAGES_DIR = Path(
    os.getenv("IMAGES_DIR", Path(__file__).resolve().parents[2] / "images")
).resolve()

app.mount("/images", StaticFiles(directory=str(IMAGES_DIR), check_dir=False), name="images")

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

SENTIMENT_SERVICE_URL = os.getenv("SENTIMENT_SERVICE_URL", "http://sentiment-analysis:8001/predict")


# ----------------------------
# NEW: TextGenJob endpoints
# ----------------------------
@app.post("/textgen/jobs", response_model=TextGenJobOut)
def start_textgen_job(payload: TextGenSuggestRequest):
    prompt = payload.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt is empty")

    job = create_textgen_job(prompt=prompt, max_new_tokens=payload.max_new_tokens)
    try:
        publish_textgen_job(job_id=job["id"], prompt=prompt, max_new_tokens=payload.max_new_tokens)
    except Exception as exc:
        # falls queue kaputt -> job auf error setzen
        set_textgen_job_result(job_id=job["id"], status="error", generated_text=None, error=str(exc))
        raise

    return job


@app.get("/textgen/jobs/{job_id}", response_model=TextGenJobOut)
def read_textgen_job(job_id: int):
    job = get_textgen_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return job


@app.put("/textgen/jobs/{job_id}", response_model=TextGenJobOut)
def update_textgen_job(job_id: int, payload: TextGenJobResultIn):
    updated = set_textgen_job_result(
        job_id=job_id,
        status=payload.status,
        generated_text=payload.generated_text,
        error=payload.error,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="job not found")
    return updated


# ----------------------------
# Posts (wie gehabt)
# ----------------------------
@app.post("/posts", response_model=PostOut, summary="Create a new post")
async def create_post(
    image: UploadFile = File(...),
    text: str = Form(...),
    user: str = Form(...),
):
    # sentiment check (kollege)
    try:
        response = requests.post(SENTIMENT_SERVICE_URL, json={"text": text}, timeout=5.0)
        response.raise_for_status()
        sentiment = response.json().get("sentiment")
        if sentiment == "Negative":
            raise HTTPException(status_code=400, detail="Negative comment not allowed")
    except requests.RequestException as e:
        print(f"Sentiment Service Error: {e}")
        pass

    base_dir = IMAGES_DIR / "original"
    base_dir.mkdir(parents=True, exist_ok=True)

    suffix = Path(image.filename).suffix or ".jpg"
    timestamp = int(datetime.now(timezone.utc).timestamp())
    filename = f"{timestamp}_{user}{suffix}"
    file_path = base_dir / filename

    content = await image.read()
    with open(file_path, "wb") as f:
        f.write(content)

    image_url = f"/images/original/{filename}"

    post_id = add_post(image=str(image_url), text=text, user=user)
    created = get_post_by_id(post_id)
    if not created:
        raise HTTPException(status_code=500, detail="Post could not be created")

    try:
        publish_image_resize(post_id, created["image"])
    except Exception as exc:
        print(f"Could not publish image resize event: {exc}")

    # ❗WICHTIG: Kein Auto-TextGen nach dem Posten mehr.
    # TextGen passiert VOR dem Posten über /textgen/jobs + Übernehmen im UI.

    return created


@app.get("/posts/latest", response_model=PostOut)
def latest_post():
    post = get_latest_post()
    if not post:
        raise HTTPException(status_code=404, detail="No posts found")
    return post


@app.get("/posts", response_model=list[PostOut])
def list_posts(user: str | None = None):
    return get_all_posts(user=user)


@app.get("/posts/search", response_model=list[PostOut])
def search(query: str):
    return search_posts(query=query)


@app.get("/posts/{post_id}", response_model=PostOut)
def get_post(post_id: int):
    post = get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post


@app.put("/posts/{post_id}/thumbnail", response_model=PostOut)
def update_thumbnail(post_id: int, payload: ThumbnailIn):
    updated = set_post_thumbnail(post_id, payload.image_small)
    if not updated:
        raise HTTPException(status_code=404, detail="Post not found")
    return updated


@app.get("/users/{user}/posts", response_model=List[PostOut])
def list_user_posts(user: str):
    return get_all_posts(user=user)


@app.delete("/posts/{post_id}", status_code=204)
def delete_post(post_id: int):
    deleted = delete_post_from_db(post_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Post not found")
    return

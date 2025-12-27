from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import List

import requests
from dotenv import load_dotenv, find_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from fastapi.concurrency import run_in_threadpool
# from .events import publish_image_resize, publish_textgen_job
from .events import publish_image_resize, publish_textgen_job, check_sentiment_rpc

# 2. ADD check_sentiment_rpc TO IMPORTS
# try:
#     from .events import publish_image_resize, publish_textgen_job, check_sentiment_rpc
# except ImportError:
#     from .events import publish_image_resize, publish_textgen_job
#     check_sentiment_rpc = None

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
import asyncio
import httpx


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

# Default: repo_root/images (wenn IMAGES_DIR nicht gesetzt ist)
DEFAULT_IMAGES = (Path(__file__).resolve().parents[3] / "images")
IMAGES_DIR = Path(os.getenv("IMAGES_DIR", str(DEFAULT_IMAGES))).resolve()

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

# SENTIMENT_SERVICE_URL = os.getenv("SENTIMENT_SERVICE_URL", "http://sentiment-analysis:8001/predict")


# ----------------------------
# TextGenJob endpoints
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
# Posts
# ----------------------------
@app.post("/posts", response_model=PostOut, summary="Create a new post")
async def create_post(
    image: UploadFile = File(...),
    text: str = Form(...),
    user: str = Form(...),
):
    """
    Flow:
    1) Sentiment-Check: Preferred RPC (RabbitMQ), Fallback HTTP
    2) Save Image & DB
    3) Trigger Resize async (RabbitMQ)
    """
    # sentiment = None

    # --- 1. SENTIMENT CHECK (RabbitMQ RPC Only) ---
    # if check_sentiment_rpc is not None:
    #     try:
    #         # We use run_in_threadpool to prevent the Python 3.12 Deadlock
    #         sentiment = await run_in_threadpool(check_sentiment_rpc, text)
    #         print(f"DEBUG: Sentiment RPC returned: {sentiment}")
    #     except Exception as e:
    #         # Now you will see this error in your local console if RabbitMQ fails
    #         print(f"ERROR: Sentiment RPC failed: {e}")
    #         sentiment = None

    # # 3. Enforce Sentiment Logic
    # if sentiment == "Negative":
    #     raise HTTPException(status_code=400, detail="Negative comment not allowed")

    # --- 1. GATEKEEPER (RPC CHECK) ---
    print(f"Checking sentiment for: {text}")
    try:
        # sentiment = check_sentiment_rpc(text) # This WAITS for the AI
        sentiment = await run_in_threadpool(check_sentiment_rpc, text)
        print(f"Sentiment Result: {sentiment}")
        
        if sentiment == "Negative":
            raise HTTPException(
                status_code=400, 
                detail="Comment rejected. Only Positive/Neutral vibes allowed!"
            )
            
    except Exception as e:
        # If it's the HTTPException we just raised, pass it through
        if isinstance(e, HTTPException): raise e
        # If RabbitMQ fails, we decide: fail safe?
        print(f"Sentiment Check Failed: {e}")
        # pass # Uncomment to allow posts even if AI is down

    # 4. Save Image to Disk
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

    # 5. Save Post to Database
    post_id = add_post(image=str(image_url), text=text, user=user)
    created = get_post_by_id(post_id)
    if not created:
        raise HTTPException(status_code=500, detail="Post could not be created")

    # 6. Trigger Image Resize (Async Background Task)
    # We use asyncio.to_thread to run the blocking Pika publish function safely
    # and create_task to ensure the API responds immediately without waiting.
    try:
        asyncio.create_task(asyncio.to_thread(publish_image_resize, post_id, created["image"]))
    except Exception:
        pass

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

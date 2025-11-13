# src/simple_social/api.py
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from .db import init_db, add_post, get_latest_post

class PostIn(BaseModel):
    image: str
    text: str
    user: str

class PostOut(PostIn):
    id: int
    created_at: datetime

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db()
    yield
    # Shutdown (optional aufräumen)

app = FastAPI(title="Simple Social", lifespan=lifespan)

@app.post("/posts", response_model=PostOut)
def create_post(post: PostIn):
    post_id = add_post(post.image, post.text, post.user)
    return get_latest_post()

@app.get("/posts/latest", response_model=PostOut)
def latest_post():
    post = get_latest_post()
    if not post:
        raise HTTPException(status_code=404, detail="No posts found")
    return post

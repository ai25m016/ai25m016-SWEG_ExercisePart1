from contextlib import asynccontextmanager
from datetime import datetime
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .db import (
    init_db,
    add_post,
    get_latest_post,
    get_all_posts,
    get_post_by_id,
    search_posts,
    delete_post as delete_post_from_db,
)


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


app = FastAPI(
    title="Simple Social",
    description="Simple Social media REST API for the course exercise.",
    lifespan=lifespan,
)

origins = [
    "http://127.0.0.1:5500",
    "http://localhost:5500",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,      # or ["*"] for quick dev tests
    allow_credentials=True,
    allow_methods=["*"],        # important: includes GET, POST, OPTIONS, ...
    allow_headers=["*"],
)

@app.post("/posts", response_model=PostOut, summary="Create a new post")
def create_post(post: PostIn):
    """
    Einen neuen Post anlegen und den gespeicherten Datensatz zurückgeben.
    """
    post_id = add_post(post.image, post.text, post.user)
    created = get_post_by_id(post_id)
    if not created:
        raise HTTPException(status_code=500, detail="Post could not be created")
    return created


@app.get("/posts/latest", response_model=PostOut, summary="Get the latest post")
def latest_post():
    """
    Den zuletzt erstellten Post zurückgeben.
    """
    post = get_latest_post()
    if not post:
        raise HTTPException(status_code=404, detail="No posts found")
    return post


@app.get("/posts", response_model=list[PostOut], summary="List posts")
def list_posts(user: str | None = None):
    """
    Alle Posts zurückgeben.

    Optionaler Query-Parameter:
    - **user**: Nur Posts eines bestimmten Users zurückgeben.
    """
    return get_all_posts(user=user)


@app.get(
    "/posts/search",
    response_model=list[PostOut],
    summary="Search posts by text",
)
def search(query: str):
    """
    Posts suchen, deren Text den Suchbegriff enthält.

    Query-Parameter:
    - **query**: Suchbegriff, der im Text vorkommen muss.
    """
    return search_posts(query=query)


@app.get("/posts/{post_id}", response_model=PostOut, summary="Get post by ID")
def get_post(post_id: int):
    """
    Einen einzelnen Post anhand seiner ID zurückgeben.
    """
    post = get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post


@app.get(
    "/users/{user}/posts",
    response_model=List[PostOut],
    summary="List posts by user",
)
def list_user_posts(user: str):
    """
    Alle Posts eines bestimmten Users zurückgeben.

    Pfadparameter:
    - **user**: Benutzername, dessen Posts aufgelistet werden sollen.
    """
    return get_all_posts(user=user)


@app.delete(
    "/posts/{post_id}",
    status_code=204,
    summary="Delete post by ID",
)
def delete_post(post_id: int):
    """
    Löscht einen Post anhand seiner ID.

    - Gibt **204 No Content** zurück, wenn der Post gelöscht wurde.
    - Gibt **404 Not Found** zurück, wenn die ID nicht existiert.
    """
    deleted = delete_post_from_db(post_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Post not found")
    # Kein Body nötig – FastAPI schickt 204 No Content
    return

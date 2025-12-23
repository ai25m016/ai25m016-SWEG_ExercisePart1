from __future__ import annotations

import os
from typing import Optional
from pathlib import Path
from datetime import datetime

from sqlmodel import SQLModel, create_engine, Session, select

from .models import Post, TextGenJob

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "social.db"
DB_PATH = Path(os.getenv("DB_PATH", str(DEFAULT_DB_PATH)))


def _create_engine():
    if os.getenv("DB_PATH"):
        return create_engine(
            f"sqlite:///{DB_PATH}",
            echo=False,
            connect_args={"check_same_thread": False},
        )

    def _running_in_docker() -> bool:
        if Path("/.dockerenv").exists():
            return True
        try:
            cgroup = Path("/proc/1/cgroup")
            if cgroup.exists() and "docker" in cgroup.read_text().lower():
                return True
        except Exception:
            pass
        return False

    database_url = os.getenv("DATABASE_URL")
    database_url_local = os.getenv("DATABASE_URL_LOCAL")

    if _running_in_docker():
        if database_url:
            return create_engine(database_url, echo=False, pool_pre_ping=True)
        if database_url_local:
            return create_engine(database_url_local, echo=False, pool_pre_ping=True)

    if database_url_local and ("@localhost" in database_url_local or "@127.0.0.1" in database_url_local):
        return create_engine(database_url_local, echo=False, pool_pre_ping=True)

    return create_engine(
        f"sqlite:///{DB_PATH}",
        echo=False,
        connect_args={"check_same_thread": False},
    )


ENGINE = _create_engine()


def get_engine():
    return ENGINE


def init_db():
    SQLModel.metadata.create_all(get_engine())


def add_post(image: str, text: str, user: str) -> int:
    with Session(get_engine()) as session:
        post = Post(
            image=image,
            image_small=None,
            text=text,
            user=user,
            created_at=datetime.now(),
        )
        session.add(post)
        session.commit()
        session.refresh(post)
        return post.id


def get_latest_post() -> dict | None:
    with Session(get_engine()) as session:
        stmt = select(Post).order_by(Post.created_at.desc(), Post.id.desc()).limit(1)
        post = session.exec(stmt).first()
        return post.model_dump() if post else None


def get_post_by_id(post_id: int) -> dict | None:
    with Session(get_engine()) as session:
        post = session.get(Post, post_id)
        return post.model_dump() if post else None


def get_all_posts(user: Optional[str] = None) -> list[dict]:
    with Session(get_engine()) as session:
        stmt = select(Post)
        if user is not None:
            stmt = stmt.where(Post.user == user)
        stmt = stmt.order_by(Post.created_at, Post.id)
        posts = session.exec(stmt).all()
        return [p.model_dump() for p in posts]


def search_posts(query: str) -> list[dict]:
    with Session(get_engine()) as session:
        stmt = select(Post).where(Post.text.contains(query))
        posts = session.exec(stmt).all()
        return [p.model_dump() for p in posts]


def delete_post(post_id: int) -> bool:
    with Session(get_engine()) as session:
        post = session.get(Post, post_id)
        if post is None:
            return False
        session.delete(post)
        session.commit()
        return True


def set_post_thumbnail(post_id: int, image_small: str) -> dict | None:
    with Session(get_engine()) as session:
        post = session.get(Post, post_id)
        if post is None:
            return None
        post.image_small = image_small
        session.add(post)
        session.commit()
        session.refresh(post)
        return post.model_dump()


# ---------------------------
# TextGenJob (Pre-Post Suggest)
# ---------------------------

def create_textgen_job(prompt: str, max_new_tokens: int) -> dict:
    with Session(get_engine()) as session:
        job = TextGenJob(
            prompt=prompt,
            max_new_tokens=max_new_tokens,
            status="pending",
            created_at=datetime.now(),
        )
        session.add(job)
        session.commit()
        session.refresh(job)
        return job.model_dump()


def get_textgen_job(job_id: int) -> dict | None:
    with Session(get_engine()) as session:
        job = session.get(TextGenJob, job_id)
        return job.model_dump() if job else None


def set_textgen_job_result(job_id: int, status: str, generated_text: str | None, error: str | None) -> dict | None:
    with Session(get_engine()) as session:
        job = session.get(TextGenJob, job_id)
        if job is None:
            return None
        job.status = status
        job.generated_text = generated_text
        job.error = error
        session.add(job)
        session.commit()
        session.refresh(job)
        return job.model_dump()

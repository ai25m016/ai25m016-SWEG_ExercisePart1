from __future__ import annotations

import os
from typing import Optional
from pathlib import Path
from datetime import datetime

from sqlmodel import SQLModel, create_engine, Session, select

from .models import Post

# Lokale SQLite-DB als Fallback
DB_PATH = Path(__file__).resolve().parent.parent.parent / "social.db"


def _create_engine():
    """Engine-Auswahl.

    Ziel:
    - Docker: PostgreSQL via DATABASE_URL ("db" Hostname ist im Docker-Netz erreichbar)
    - Lokal: NICHT versuchen, auf Host "db" zu verbinden (würde scheitern) → SQLite-Fallback
      Optional: wenn DATABASE_URL_LOCAL auf localhost/127.0.0.1 zeigt, kann lokal auch Postgres genutzt werden.
    """

    def _running_in_docker() -> bool:
        # Standard-Indikator in Docker
        if Path("/.dockerenv").exists():
            return True
        # Fallback: cgroup-Hinweise (Linux)
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
        # In Docker ist "db" ein gültiger Hostname (docker-compose).
        if database_url:
            return create_engine(database_url, echo=False, pool_pre_ping=True)
        if database_url_local:
            return create_engine(database_url_local, echo=False, pool_pre_ping=True)

    # Außerhalb von Docker: "db" ist i.d.R. NICHT erreichbar. Nur nutzen, wenn explizit localhost.
    if database_url_local and ("@localhost" in database_url_local or "@127.0.0.1" in database_url_local):
        return create_engine(database_url_local, echo=False, pool_pre_ping=True)

    # Lokaler Fallback: SQLite
    return create_engine(
        f"sqlite:///{DB_PATH}",
        echo=False,
        connect_args={"check_same_thread": False},
    )


# Ein globales Engine-Objekt wiederverwenden
ENGINE = _create_engine()


def get_engine():
    return ENGINE


def init_db():
    SQLModel.metadata.create_all(get_engine())


def add_post(image: str, text: str, user: str) -> int:
    """Neuen Post anlegen und die ID zurückgeben."""
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
    """Neuesten Post nach created_at (und id) zurückgeben."""
    with Session(get_engine()) as session:
        stmt = (
            select(Post)
            .order_by(Post.created_at.desc(), Post.id.desc())
            .limit(1)
        )
        post = session.exec(stmt).first()
        return post.model_dump() if post else None


def get_post_by_id(post_id: int) -> dict | None:
    """Einen einzelnen Post per ID holen."""
    with Session(get_engine()) as session:
        post = session.get(Post, post_id)
        return post.model_dump() if post else None


def get_all_posts(user: Optional[str] = None) -> list[dict]:
    """
    Alle Posts zurückgeben, optional gefiltert nach user.
    """
    with Session(get_engine()) as session:
        stmt = select(Post)
        if user is not None:
            stmt = stmt.where(Post.user == user)
        stmt = stmt.order_by(Post.created_at, Post.id)
        posts = session.exec(stmt).all()
        return [p.model_dump() for p in posts]


def search_posts(query: str) -> list[dict]:
    """
    Posts zurückgeben, bei denen der Text die query enthält.
    """
    with Session(get_engine()) as session:
        stmt = select(Post).where(Post.text.contains(query))
        posts = session.exec(stmt).all()
        return [p.model_dump() for p in posts]


def delete_post(post_id: int) -> bool:
    """
    Löscht einen Post mit der gegebenen ID.
    Gibt True zurück, wenn etwas gelöscht wurde,
    sonst False (Post nicht gefunden).
    """
    with Session(get_engine()) as session:
        post = session.get(Post, post_id)
        if post is None:
            return False
        session.delete(post)
        session.commit()
        return True

def set_post_thumbnail(post_id: int, image_small: str) -> dict | None:
    """
    Setzt das verkleinerte Bild für einen Post.
    Wird vom Image-Resizer-Service aufgerufen.
    """
    with Session(get_engine()) as session:
        post = session.get(Post, post_id)
        if post is None:
            return None

        post.image_small = image_small
        session.add(post)
        session.commit()
        session.refresh(post)
        return post.model_dump()

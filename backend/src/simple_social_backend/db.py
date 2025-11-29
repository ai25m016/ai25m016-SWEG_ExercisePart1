from typing import Optional
from pathlib import Path
from datetime import datetime

from sqlmodel import SQLModel, create_engine, Session, select

from .models import Post

DB_PATH = Path(__file__).resolve().parent.parent.parent / "social.db"


def get_engine():
    return create_engine(f"sqlite:///{DB_PATH}", echo=False)


def init_db():
    SQLModel.metadata.create_all(get_engine())


def add_post(image: str, text: str, user: str) -> int:
    """Neuen Post anlegen und die ID zurückgeben."""
    with Session(get_engine()) as session:
        post = Post(image=image, text=text, user=user, created_at=datetime.now())
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

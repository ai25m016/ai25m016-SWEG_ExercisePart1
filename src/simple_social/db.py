from sqlmodel import SQLModel, create_engine, Session, select
from pathlib import Path
from datetime import datetime
from .models import Post

DB_PATH = Path(__file__).resolve().parent.parent.parent / "social.db"

def get_engine():
    return create_engine(f"sqlite:///{DB_PATH}", echo=False)

def init_db():
    SQLModel.metadata.create_all(get_engine())

def add_post(image: str, text: str, user: str) -> int:
    with Session(get_engine()) as session:
        post = Post(image=image, text=text, user=user, created_at=datetime.now())
        session.add(post)
        session.commit()
        session.refresh(post)
        return post.id

def get_latest_post() -> dict | None:
    with Session(get_engine()) as session:
        stmt = select(Post).order_by(Post.created_at.desc(), Post.id.desc()).limit(1)
        post = session.exec(stmt).first()
        return post.model_dump() if post else None

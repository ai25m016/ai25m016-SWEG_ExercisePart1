from __future__ import annotations

from datetime import datetime
from sqlmodel import SQLModel, Field


class Post(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)

    image: str
    image_small: str | None = None

    text: str
    user: str
    created_at: datetime | None = Field(default=None)

    # optional: falls du nach dem Posten auch noch TextGen speichern willst
    generated_text: str | None = None
    generated_text_status: str | None = None   # "pending" | "done" | "error"
    generated_text_prompt: str | None = None
    generated_text_error: str | None = None


class TextGenJob(SQLModel, table=True):
    """
    Job für 'Kommentar vorschlagen' VOR dem Posten.
    Wird per Queue abgearbeitet, Ergebnis wird gespeichert.
    """
    id: int | None = Field(default=None, primary_key=True)
    prompt: str
    max_new_tokens: int = 60

    status: str = "pending"  # pending | done | error
    generated_text: str | None = None
    error: str | None = None

    created_at: datetime | None = Field(default=None)

from datetime import datetime
from sqlmodel import SQLModel, Field

class Post(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)

    # Pfad/URL zum Originalbild
    image: str

    # Pfad/URL zum verkleinerten Bild (wird erst später gesetzt)
    image_small: str | None = None

    text: str
    user: str
    created_at: datetime | None = Field(default=None)
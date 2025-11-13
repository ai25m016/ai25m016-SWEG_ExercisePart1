from datetime import datetime
from sqlmodel import SQLModel, Field

class Post(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    image: str
    text: str
    user: str
    created_at: datetime | None = Field(default=None)

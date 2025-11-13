from .db import init_db, add_post
import os
from pathlib import Path
import uvicorn

def seed():
    init_db()
    add_post("images/cat.png",  "Süße Katze!",            "alice")
    add_post("images/lake.jpg", "Spaziergang am See.",    "bob")
    add_post("images/meal.jpg", "Veganes Mittagessen 😋", "carol")
    print("Seeded 3 posts.")

def start_api():
    # PYTHONPATH für src setzen, falls nötig
    src_path = Path(__file__).resolve().parents[1]  # .../simple_social/src
    os.environ.setdefault("PYTHONPATH", str(src_path))

    uvicorn.run(
        "simple_social.api:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        reload_dirs=[str(src_path)],
    )

if __name__ == "__main__":
    seed()      # nur falls du mal direkt `python cli.py` startest

import os
from pathlib import Path
import uvicorn
from dotenv import load_dotenv

def _load_env_local():
    # backend/src/simple_social_backend/cli.py -> parents[2] == backend/
    backend_root = Path(__file__).resolve().parents[2]
    env_file = backend_root / ".env.local"
    if env_file.exists():
        load_dotenv(env_file, override=False)

def seed():
    _load_env_local()
    from .db import init_db, add_post
    init_db()
    add_post("images/cat.png",  "Süße Katze!",            "alice")
    add_post("images/lake.jpg", "Spaziergang am See.",    "bob")
    add_post("images/meal.jpg", "Veganes Mittagessen 😋", "carol")
    print("Seeded 3 posts.")

def start_api():
    _load_env_local()

    src_dir = Path(__file__).resolve().parents[1]  # .../backend/src
    uvicorn.run(
        "simple_social_backend.main:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8000")),
        reload=True,
        reload_dirs=[str(src_dir)],
    )

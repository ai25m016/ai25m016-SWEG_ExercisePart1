import os
import time
import subprocess
from pathlib import Path

import pytest
from dotenv import dotenv_values


def _run(cmd: list[str]) -> None:
    subprocess.check_call(cmd)


def _pick_compose_file(repo_root: Path) -> Path:
    candidates = [
        repo_root / "docker-compose.local.yml",
        repo_root / "docker-compose.yml",
    ]
    for f in candidates:
        if f.exists():
            return f
    raise FileNotFoundError(
        f"Kein Compose-File gefunden. Erwartet im Repo-Root: {candidates}"
    )


def _wait_pg_isready(
    compose_file: Path,
    service: str,
    user: str,
    dbname: str,
    timeout_s: int = 120,
) -> None:
    end = time.time() + timeout_s
    last = None
    while time.time() < end:
        try:
            subprocess.check_call(
                [
                    "docker", "compose", "-f", str(compose_file),
                    "exec", "-T", service,
                    "pg_isready", "-U", user, "-d", dbname
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return
        except Exception as e:
            last = repr(e)
            time.sleep(0.5)
    raise RuntimeError(f"Postgres nicht ready nach {timeout_s}s. last={last}")


@pytest.fixture(scope="session")
def docker_postgres():
    """
    Startet IMMER docker compose db und stoppt IMMER am Ende (down -v).
    DB-Name/User/Password kommen aus .env im Repo-Root.
    """
    repo_root = Path(__file__).resolve().parents[2]  # backend/tests -> repo root ✅
    compose_file = _pick_compose_file(repo_root)
    env_file = repo_root / ".env"

    env = dotenv_values(env_file) if env_file.exists() else {}

    db_name_base = env.get("DB_NAME", os.getenv("DB_NAME", "simple_social"))
    db_user_base = env.get("DB_USER", os.getenv("DB_USER", "simple_social"))
    db_pw = env.get("DB_PASSWORD", os.getenv("DB_PASSWORD", "supersecret"))

    dbname = f"{db_name_base}_LOCAL"
    dbuser = f"{db_user_base}_LOCAL"

    print(f"[docker_postgres] compose_file={compose_file}", flush=True)
    print("[docker_postgres] starting db via docker compose...", flush=True)
    _run(["docker", "compose", "-f", str(compose_file), "up", "-d", "db"])

    print("[docker_postgres] waiting for pg_isready...", flush=True)
    _wait_pg_isready(
        compose_file=compose_file,
        service="db",
        user=dbuser,
        dbname=dbname,
        timeout_s=120,
    )
    print("[docker_postgres] postgres is ready ✅", flush=True)

    yield {"db_name": dbname, "db_user": dbuser, "db_password": db_pw}

    print("[docker_postgres] stopping db (down -v)...", flush=True)
    _run(["docker", "compose", "-f", str(compose_file), "down", "-v"])
    print("[docker_postgres] stopped ✅", flush=True)


@pytest.fixture(autouse=True)
def _auto_db_for_api(request):
    """
    Für alle Tests mit Marker 'api' wird automatisch Postgres hochgefahren.
    """
    if request.node.get_closest_marker("api"):
        request.getfixturevalue("docker_postgres")

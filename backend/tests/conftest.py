# backend/tests/conftest.py
import os
import time
import subprocess
from pathlib import Path

import pytest
import requests


# ----------------------------
# Helpers: repo / compose
# ----------------------------

def _find_repo_root() -> Path:
    here = Path(__file__).resolve()
    for p in [here] + list(here.parents):
        if (p / "docker-compose.local.yml").exists() or (p / "docker-compose.yml").exists():
            return p
    # Fallback: typical layout repo/backend/tests/conftest.py -> repo is parents[2]
    return here.parents[2]


def _pick_compose_file(repo_root: Path) -> Path:
    override = os.getenv("E2E_COMPOSE_FILE") or os.getenv("COMPOSE_FILE")
    if override:
        return Path(override).resolve()

    cand = [repo_root / "docker-compose.local.yml", repo_root / "docker-compose.yml"]
    for f in cand:
        if f.exists():
            return f
    raise FileNotFoundError("Kein Compose-File im Repo-Root gefunden (docker-compose.local.yml / docker-compose.yml).")


def _dc_base(repo_root: Path, compose_file: Path) -> list[str]:
    # IMPORTANT: this must be a flat list of strings (no nested lists!)
    return ["docker", "compose", "--project-directory", str(repo_root), "-f", str(compose_file)]


def _run(cmd: list[str]) -> None:
    subprocess.check_call(cmd)


def _out(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, text=True).strip()


def _compose_services(dc: list[str]) -> set[str]:
    out = subprocess.check_output(dc + ["config", "--services"], text=True)
    return {line.strip() for line in out.splitlines() if line.strip()}


def _pick_service(services: set[str], preferred: str, contains: list[str]) -> str | None:
    if preferred in services:
        return preferred
    low = {s: s.lower() for s in services}
    for s, sl in low.items():
        if any(c in sl for c in contains):
            return s
    return None


def _service_is_running(dc: list[str], service: str) -> bool:
    # docker compose ps -q <service> -> container id (if running)
    try:
        cid = _out(dc + ["ps", "-q", service])
        return bool(cid)
    except Exception:
        return False


# ----------------------------
# Waiters
# ----------------------------

def _wait_pg_isready(dc: list[str], db_service: str, timeout_s: int = 90) -> None:
    end = time.time() + timeout_s
    last = None
    while time.time() < end:
        try:
            _run(dc + ["exec", "-T", db_service, "pg_isready"])
            return
        except Exception as e:
            last = repr(e)
            time.sleep(1)
    raise RuntimeError(f"Postgres not ready (last={last})")


def _wait_http_ok(url: str, timeout_s: int = 150) -> None:
    end = time.time() + timeout_s
    last = None
    while time.time() < end:
        try:
            r = requests.get(url, timeout=2)
            # < 500 means server answers (even 404/401 is fine for "up")
            if r.status_code < 500:
                return
            last = f"HTTP {r.status_code}"
        except Exception as e:
            last = repr(e)
        time.sleep(2)
    raise RuntimeError(f"Service not ready: {url} (last={last})")


def _get_env(dc: list[str], service: str, key: str) -> str | None:
    try:
        val = _out(dc + ["exec", "-T", service, "printenv", key])
        return val if val else None
    except Exception:
        return None


def _get_host_port(dc: list[str], service: str, container_port: int = 5432) -> int:
    # Example: "0.0.0.0:5432" or "127.0.0.1:5433"
    s = _out(dc + ["port", service, str(container_port)])
    return int(s.rsplit(":", 1)[-1])


# ----------------------------
# Base fixtures
# ----------------------------

@pytest.fixture(scope="session")
def repo_root() -> Path:
    return _find_repo_root()


@pytest.fixture(scope="session")
def compose_file(repo_root: Path) -> Path:
    return _pick_compose_file(repo_root)


# ----------------------------
# Persistence/API: Postgres only
# ----------------------------

@pytest.fixture(scope="session")
def docker_postgres(repo_root: Path, compose_file: Path):
    dc = _dc_base(repo_root, compose_file)
    services = _compose_services(dc)

    db_service = _pick_service(services, "db", ["postgres", "db"])
    if not db_service:
        raise RuntimeError(f"Kein DB-Service gefunden. Services={sorted(services)}")

    print(f"[docker_postgres] compose_file={compose_file}", flush=True)

    _run(dc + ["down", "-v"])
    _run(dc + ["up", "-d", "--build", db_service])
    _wait_pg_isready(dc, db_service, timeout_s=90)

    db_name = _get_env(dc, db_service, "POSTGRES_DB") or "postgres"
    db_user = _get_env(dc, db_service, "POSTGRES_USER") or "postgres"
    db_password = _get_env(dc, db_service, "POSTGRES_PASSWORD") or ""
    host_port = _get_host_port(dc, db_service, 5432)

    print(
        f"[docker_postgres] ready ✅ service={db_service} user={db_user} db={db_name} port={host_port}",
        flush=True,
    )

    yield {
        "db_name": db_name,
        "db_user": db_user,
        "db_password": db_password,
        "service": db_service,
        "host": "127.0.0.1",
        "port": host_port,
    }

    _run(dc + ["down", "-v"])
    print("[docker_postgres] stopped ✅", flush=True)


# ----------------------------
# Resizer E2E: start backend stack (minimal)
# ----------------------------

BASE_URL = os.getenv("RESIZER_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


@pytest.fixture(scope="session")
def backend_server(repo_root: Path, compose_file: Path):
    """
    Must return dict with key 'base' because test_resizer.py does backend_server['base'].
    Starts a minimal set of services needed for /posts + image resize pipeline.
    """
    dc = _dc_base(repo_root, compose_file)
    services = _compose_services(dc)

    backend_svc = _pick_service(services, "backend", ["backend", "api"])
    resizer_svc = _pick_service(services, "image-resizer", ["image-resizer", "image_resizer", "resizer"])
    db_svc = _pick_service(services, "db", ["postgres", "db"])
    rabbit_svc = _pick_service(services, "rabbitmq", ["rabbit", "mq", "rabbitmq"])

    if not backend_svc:
        raise RuntimeError(f"Kein Backend-Service gefunden. Services={sorted(services)}")

    # Build list: only what exists in compose
    up_list: list[str] = []
    for s in [db_svc, rabbit_svc, resizer_svc, backend_svc]:
        if s and s not in up_list:
            up_list.append(s)

    print(f"[backend_server] bringing up: {up_list}", flush=True)

    _run(dc + ["down", "-v"])
    _run(dc + ["up", "-d", "--build", *up_list])

    # backend reachable
    _wait_http_ok(f"{BASE_URL}/docs", timeout_s=150)

    yield {"base": BASE_URL}

    _run(dc + ["down", "-v"])
    print("[backend_server] stopped ✅", flush=True)


@pytest.fixture(scope="session")
def resizer_process(repo_root: Path, compose_file: Path):
    """
    Exists because test_resizer.py depends on it.
    Should NOT restart the whole stack.
    Only ensures resizer service is running if present.
    """
    dc = _dc_base(repo_root, compose_file)
    services = _compose_services(dc)

    resizer_svc = _pick_service(
        services,
        "image-resizer",
        ["image-resizer", "image_resizer", "resizer"],
    )

    if not resizer_svc:
        yield
        return

    # ensure running (no rebuild)
    if not _service_is_running(dc, resizer_svc):
        _run(dc + ["up", "-d", resizer_svc])

    yield

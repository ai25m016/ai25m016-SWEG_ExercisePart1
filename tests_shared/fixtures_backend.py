from __future__ import annotations

import os
from pathlib import Path

import pytest

from tests_shared.docker_compose import (
    find_repo_root, pick_compose_file, dc_base, run, out,
    services, pick_service, is_running,
    wait_pg_isready, wait_http_ok,
    get_env, host_port,
)

BASE_URL = os.getenv("RESIZER_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


@pytest.fixture(scope="session")
def repo_root() -> Path:
    # wichtig: starte Suche “von hier” (wo das Plugin liegt)
    return find_repo_root(Path(__file__))


@pytest.fixture(scope="session")
def compose_file(repo_root: Path) -> Path:
    return pick_compose_file(repo_root)


def _build_pg_url(cfg: dict) -> str:
    return f"postgresql+psycopg://{cfg['db_user']}:{cfg['db_password']}@{cfg['host']}:{cfg['port']}/{cfg['db_name']}"


@pytest.fixture(scope="session")
def docker_postgres(repo_root: Path, compose_file: Path):
    dc = dc_base(repo_root, compose_file)
    svcs = services(dc)

    db_service = pick_service(svcs, "db", ["postgres", "db"])
    if not db_service:
        raise RuntimeError(f"Kein DB-Service gefunden. Services={sorted(svcs)}")

    run(dc + ["down", "-v"])
    run(dc + ["up", "-d", "--build", db_service])
    wait_pg_isready(dc, db_service, timeout_s=90)

    cfg = {
        "db_name": get_env(dc, db_service, "POSTGRES_DB") or "postgres",
        "db_user": get_env(dc, db_service, "POSTGRES_USER") or "postgres",
        "db_password": get_env(dc, db_service, "POSTGRES_PASSWORD") or "",
        "service": db_service,
        "host": "127.0.0.1",
        "port": host_port(dc, db_service, 5432),
    }
    yield cfg

    run(dc + ["down", "-v"])


@pytest.fixture(scope="session")
def backend_server(repo_root: Path, compose_file: Path):
    dc = dc_base(repo_root, compose_file)
    svcs = services(dc)

    backend_svc = pick_service(svcs, "backend", ["backend", "api"])
    resizer_svc = pick_service(svcs, "image-resizer", ["image-resizer", "image_resizer", "resizer"])
    db_svc = pick_service(svcs, "db", ["postgres", "db"])
    rabbit_svc = pick_service(svcs, "rabbitmq", ["rabbit", "mq", "rabbitmq"])

    if not backend_svc:
        raise RuntimeError(f"Kein Backend-Service gefunden. Services={sorted(svcs)}")

    up_list: list[str] = []
    for s in [db_svc, rabbit_svc, resizer_svc, backend_svc]:
        if s and s not in up_list:
            up_list.append(s)

    run(dc + ["down", "-v"])
    run(dc + ["up", "-d", "--build", *up_list])

    wait_http_ok(f"{BASE_URL}/docs", timeout_s=150, dc=dc, logs_service=backend_svc)

    yield {"base": BASE_URL}

    run(dc + ["down", "-v"])


@pytest.fixture(scope="session")
def resizer_process(repo_root: Path, compose_file: Path):
    dc = dc_base(repo_root, compose_file)
    svcs = services(dc)

    resizer_svc = pick_service(svcs, "image-resizer", ["image-resizer", "image_resizer", "resizer"])
    if not resizer_svc:
        yield
        return

    if not is_running(dc, resizer_svc):
        run(dc + ["up", "-d", resizer_svc])

    yield


@pytest.fixture(autouse=True)
def disable_rabbitmq_for_local_api_tests(request):
    # Marker-Logik wie bei dir: api-tests sollen Rabbit nicht wirklich kontaktieren
    if request.node.get_closest_marker("api"):
        os.environ.setdefault("RABBITMQ_HOST", "disabled")
        os.environ.setdefault("RABBITMQ_USER", "disabled")
        os.environ.setdefault("RABBITMQ_PASSWORD", "disabled")
    yield


def _init_schema_via_project_hook() -> None:
    import simple_social_backend.db as db
    if callable(getattr(db, "init_db", None)):
        db.init_db()
        return
    raise RuntimeError("simple_social_backend.db.init_db() fehlt.")


@pytest.fixture()
def client(docker_postgres):
    pg_url = _build_pg_url(docker_postgres)

    os.environ["DATABASE_URL"] = pg_url
    os.environ["SQLALCHEMY_DATABASE_URL"] = pg_url
    os.environ.pop("DATABASE_URL_LOCAL", None)

    import importlib
    import simple_social_backend.db as db
    importlib.reload(db)

    _init_schema_via_project_hook()

    import simple_social_backend.api as api
    importlib.reload(api)

    from fastapi.testclient import TestClient
    return TestClient(api.app)

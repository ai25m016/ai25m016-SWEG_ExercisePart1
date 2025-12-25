# backend/tests/conftest.py
import os
import time
import subprocess
from pathlib import Path

import pytest


def _find_repo_root() -> Path:
    here = Path(__file__).resolve()
    for p in [here] + list(here.parents):
        if (p / "docker-compose.local.yml").exists() or (p / "docker-compose.yml").exists():
            return p
    return here.parents[2]


def _pick_compose_file(repo_root: Path) -> Path:
    for f in [repo_root / "docker-compose.local.yml", repo_root / "docker-compose.yml"]:
        if f.exists():
            return f
    raise FileNotFoundError("Kein Compose-File im Repo-Root gefunden.")


def _dc_base(repo_root: Path, compose_file: Path) -> list[str]:
    return [
        "docker", "compose",
        "--project-directory", str(repo_root),
        "-f", str(compose_file),
    ]


def _run(cmd: list[str]) -> None:
    subprocess.check_call(cmd)


def _compose_services(repo_root: Path, compose_file: Path) -> list[str]:
    dc = _dc_base(repo_root, compose_file)
    out = subprocess.check_output(dc + ["config", "--services"], text=True)
    return [line.strip() for line in out.splitlines() if line.strip()]


def _pick_service(services: list[str], preferred: str, contains: list[str]) -> str | None:
    if preferred in services:
        return preferred
    low = {s: s.lower() for s in services}
    for s, sl in low.items():
        if any(c in sl for c in contains):
            return s
    return None


def _wait_http_ok(url: str, timeout_s: int = 120) -> None:
    import requests

    end = time.time() + timeout_s
    last = None
    while time.time() < end:
        try:
            r = requests.get(url, timeout=2)
            if r.status_code == 200:
                return
            last = f"status={r.status_code}"
        except Exception as e:
            last = repr(e)
        time.sleep(1)
    raise RuntimeError(f"Service not ready: {url} (last={last})")


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return _find_repo_root()


@pytest.fixture(scope="session")
def compose_file(repo_root: Path) -> Path:
    return _pick_compose_file(repo_root)


@pytest.fixture(scope="session")
def e2e_stack(repo_root: Path, compose_file: Path):
    base = os.getenv("E2E_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    dc = _dc_base(repo_root, compose_file)

    services = _compose_services(repo_root, compose_file)

    db = _pick_service(services, "db", ["postgres", "db"])
    backend = _pick_service(services, "backend", ["backend", "api"])
    rabbit = _pick_service(services, "rabbitmq", ["rabbit", "mq"])
    resizer = _pick_service(services, "resizer", ["resizer", "resize"])

    # Minimal-Anforderung
    if not db or not backend:
        raise RuntimeError(f"Compose Services gefunden: {services}\n"
                           f"Aber db/backend konnte nicht erkannt werden (db={db}, backend={backend}).")

    needed = [db, backend]
    if rabbit:
        needed.append(rabbit)
    if resizer:
        needed.append(resizer)

    print(f"[e2e_stack] repo_root={repo_root}", flush=True)
    print(f"[e2e_stack] compose_file={compose_file}", flush=True)
    print(f"[e2e_stack] services={services}", flush=True)
    print(f"[e2e_stack] starting={needed}", flush=True)

    _run(dc + ["down", "-v"])
    _run(dc + ["up", "-d", "--build", *needed])

    _wait_http_ok(f"{base}/docs", timeout_s=150)
    print("[e2e_stack] backend ready ✅", flush=True)

    yield {"base": base}

    _run(dc + ["down", "-v"])
    print("[e2e_stack] stopped ✅", flush=True)


@pytest.fixture(autouse=True)
def _auto_stack_for_e2e(request):
    if request.node.get_closest_marker("resizer"):
        request.getfixturevalue("e2e_stack")

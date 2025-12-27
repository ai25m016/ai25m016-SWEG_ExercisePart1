from __future__ import annotations

import os
import time
import subprocess
from pathlib import Path


def find_repo_root(start: Path) -> Path:
    here = start.resolve()
    for p in [here] + list(here.parents):
        if (p / "docker-compose.yml").exists() or (p / "docker-compose.yml").exists():
            return p
    return here.parents[2]


def pick_compose_file(repo_root: Path) -> Path:
    override = os.getenv("E2E_COMPOSE_FILE") or os.getenv("COMPOSE_FILE")
    if override:
        return Path(override).resolve()

    for f in (repo_root / "docker-compose.yml", repo_root / "docker-compose.yml"):
        if f.exists():
            return f
    raise FileNotFoundError("Kein docker-compose.yml oder docker-compose.yml gefunden.")


def dc_base(repo_root: Path, compose_file: Path) -> list[str]:
    return ["docker", "compose", "--project-directory", str(repo_root), "-f", str(compose_file)]


def run(cmd: list[str]) -> None:
    subprocess.check_call(cmd)


def out(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, text=True).strip()


def services(dc: list[str]) -> set[str]:
    txt = subprocess.check_output(dc + ["config", "--services"], text=True)
    return {line.strip() for line in txt.splitlines() if line.strip()}


def pick_service(svcs: set[str], preferred: str, contains: list[str]) -> str | None:
    if preferred in svcs:
        return preferred
    low = {s: s.lower() for s in svcs}
    for s, sl in low.items():
        if any(c in sl for c in contains):
            return s
    return None


def is_running(dc: list[str], service: str) -> bool:
    try:
        return bool(out(dc + ["ps", "-q", service]))
    except Exception:
        return False


def wait_pg_isready(dc: list[str], db_service: str, timeout_s: int = 90) -> None:
    end = time.time() + timeout_s
    last = None
    while time.time() < end:
        try:
            run(dc + ["exec", "-T", db_service, "pg_isready"])
            return
        except Exception as e:
            last = repr(e)
            time.sleep(1)
    raise RuntimeError(f"Postgres not ready (last={last})")


def wait_http_ok(url: str, *, timeout_s: int = 150, dc: list[str] | None = None, logs_service: str = "backend") -> None:
    import requests

    end = time.time() + timeout_s
    last = None
    while time.time() < end:
        try:
            r = requests.get(url, timeout=2)
            if r.status_code < 500:
                return
            last = f"HTTP {r.status_code}"
        except Exception as e:
            last = repr(e)
        time.sleep(2)

    if dc is not None:
        print("[debug] docker compose ps:", flush=True)
        try:
            run(dc + ["ps"])
        except Exception:
            pass
        print(f"[debug] docker compose logs {logs_service}:", flush=True)
        try:
            run(dc + ["logs", "--no-color", "--tail=200", logs_service])
        except Exception:
            pass

    raise RuntimeError(f"Service not ready: {url} (last={last})")


def get_env(dc: list[str], service: str, key: str) -> str | None:
    try:
        v = out(dc + ["exec", "-T", service, "printenv", key])
        return v if v else None
    except Exception:
        return None


def host_port(dc: list[str], service: str, container_port: int = 5432) -> int:
    s = out(dc + ["port", service, str(container_port)])
    return int(s.rsplit(":", 1)[-1])

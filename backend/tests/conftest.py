import os
import sys
import time
import socket
import subprocess
from pathlib import Path

import shutil
import pytest
import requests
import pika

@pytest.fixture(scope="session", autouse=True)
def set_test_env():
    # This disables actual RabbitMQ connections for ALL tests
    os.environ["DISABLE_QUEUE"] = "true"
    yield
    del os.environ["DISABLE_QUEUE"]

def _wait_amqp_ready(host: str, user: str, pw: str, timeout_s: int = 120):
    end = time.time() + timeout_s
    last = None

    creds = pika.PlainCredentials(user, pw)
    params = pika.ConnectionParameters(host=host, credentials=creds)

    while time.time() < end:
        try:
            c = pika.BlockingConnection(params)
            c.close()
            return
        except Exception as e:
            last = repr(e)
            time.sleep(0.5)

    raise RuntimeError(f"RabbitMQ AMQP not ready: {last}")

def _wait_http(url: str, timeout_s: int = 120):
    end = time.time() + timeout_s
    last = None
    while time.time() < end:
        try:
            r = requests.get(url, timeout=2)
            if r.status_code < 500:
                return
            last = f"{r.status_code} {r.text[:200]}"
        except Exception as e:
            last = repr(e)
        time.sleep(0.5)
    raise RuntimeError(f"Service not ready: {url} (last={last})")


def _port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


@pytest.fixture(scope="session")
def rabbitmq():
    """
    Reuse local RabbitMQ if something already listens on 127.0.0.1:5672,
    otherwise start docker container on that port.
    """
    host, port = "127.0.0.1", 5672
    if _port_open(host, port):
        _wait_amqp_ready(host, "test", "test", 120)

        yield {"host": host, "port": port}
        return

    # start container
    name = "rabbitmq-e2e"
    subprocess.run(["docker", "rm", "-f", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.check_call([
        "docker", "run", "-d", "--rm",
        "--name", name,
        "-p", "5672:5672",
        "-p", "15672:15672",
        "-e", "RABBITMQ_DEFAULT_USER=test",
        "-e", "RABBITMQ_DEFAULT_PASS=test",
        "rabbitmq:3-management"
    ])

    try:
        # wait until port open
        end = time.time() + 30
        while time.time() < end and not _port_open(host, port):
            time.sleep(0.5)
        if not _port_open(host, port):
            raise RuntimeError("RabbitMQ did not start on 5672")
        _wait_amqp_ready(host, "test", "test", 120)
        yield {"host": host, "port": port}
    finally:
        subprocess.run(["docker", "rm", "-f", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


@pytest.fixture
def backend_server(tmp_path, rabbitmq):
    """
    Starts backend on 127.0.0.1:8001 with isolated IMAGES_DIR in tmp.
    """
    E2E_EXTERNAL = os.getenv("E2E_EXTERNAL") == "1"
    if E2E_EXTERNAL:
        # ... (keep existing external logic) ...
        base = os.getenv("BACKEND_BASE_URL", "http://127.0.0.1:8000")
        _wait_http(f"{base}/posts", timeout_s=120)

        images_dir = tmp_path / "images"
        (images_dir / "original").mkdir(parents=True, exist_ok=True)
        (images_dir / "thumbs").mkdir(parents=True, exist_ok=True)

        try:
            yield {"base": base, "images_dir": str(images_dir), "proc": None}
        finally:
            # ... (keep cleanup logic) ...
            for _ in range(30):
                try:
                    shutil.rmtree(images_dir)
                    break
                except FileNotFoundError:
                    break
                except PermissionError:
                    time.sleep(0.1)
        return

    repo_root = Path(__file__).resolve().parents[2]
    backend_dir = repo_root / "backend"

    images_dir = tmp_path / "images"
    (images_dir / "original").mkdir(parents=True, exist_ok=True)
    (images_dir / "thumbs").mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    
    # --- [FIX START] ---
    # We must enable the queue for the E2E backend process!
    if "DISABLE_QUEUE" in env:
        del env["DISABLE_QUEUE"]
    # --- [FIX END] ---

    db_file = tmp_path / "test_social.db"
    env["DB_PATH"] = str(db_file)
    # env["RABBITMQ_HOST"] = rabbitmq["host"]
    env["RABBITMQ_HOST"] = "127.0.0.1" 
    env["IMAGE_RESIZE_QUEUE"] = env.get("IMAGE_RESIZE_QUEUE", "image_resize")
    env["BACKEND_BASE_URL"] = "http://127.0.0.1:8001"
    env["RABBITMQ_USER"] = "test"
    env["RABBITMQ_PASSWORD"] = "test"

    # IMPORTANT: your backend expects IMAGES_DIR relative to cwd ("images") OR absolute.
    # We run with cwd=backend/ and point IMAGES_DIR to that temp dir.
    env["IMAGES_DIR"] = str(images_dir)

    # start backend (no uv, just your venv python)
    cmd = [sys.executable, "-m", "uvicorn", "simple_social_backend.api:app", "--host", "127.0.0.1", "--port", "8001"]
    env["PYTHONUNBUFFERED"] = "1"
    p = subprocess.Popen(cmd, cwd=str(backend_dir), env=env)


    try:
        _wait_http("http://127.0.0.1:8001/posts", timeout_s=120)
        yield {"base": "http://127.0.0.1:8001", "images_dir": str(images_dir), "proc": p}
    finally:
        p.terminate()
        try:
            p.wait(timeout=10)
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait(timeout=5)

        wal = Path(str(db_file) + "-wal")
        shm = Path(str(db_file) + "-shm")

        # DB cleanup
        for f in [db_file, wal, shm]:
            for _ in range(30):
                try:
                    f.unlink()
                    break
                except FileNotFoundError:
                    break
                except PermissionError:
                    time.sleep(0.1)

        # images cleanup
        for _ in range(30):
            try:
                shutil.rmtree(images_dir)
                break
            except FileNotFoundError:
                break
            except PermissionError:
                time.sleep(0.1)

# @pytest.fixture
# def backend_server(tmp_path, rabbitmq):
#     """
#     Starts backend on 127.0.0.1:8001 with isolated IMAGES_DIR in tmp.
#     """
#     E2E_EXTERNAL = os.getenv("E2E_EXTERNAL") == "1"
#     if E2E_EXTERNAL:
#         base = os.getenv("BACKEND_BASE_URL", "http://127.0.0.1:8000")
#         _wait_http(f"{base}/posts", timeout_s=120)
# 
#         images_dir = tmp_path / "images"
#         (images_dir / "original").mkdir(parents=True, exist_ok=True)
#         (images_dir / "thumbs").mkdir(parents=True, exist_ok=True)
# 
#         try:
#             yield {"base": base, "images_dir": str(images_dir), "proc": None}
#         finally:
#             for _ in range(30):
#                 try:
#                     shutil.rmtree(images_dir)
#                     break
#                 except FileNotFoundError:
#                     break
#                 except PermissionError:
#                     time.sleep(0.1)
#         return
#     repo_root = Path(__file__).resolve().parents[2]
#     backend_dir = repo_root / "backend"
# 
#     images_dir = tmp_path / "images"
#     (images_dir / "original").mkdir(parents=True, exist_ok=True)
#     (images_dir / "thumbs").mkdir(parents=True, exist_ok=True)
# 
#     env = os.environ.copy()
#     db_file = tmp_path / "test_social.db"
#     env["DB_PATH"] = str(db_file)
#     env["RABBITMQ_HOST"] = rabbitmq["host"]
#     env["IMAGE_RESIZE_QUEUE"] = env.get("IMAGE_RESIZE_QUEUE", "image_resize")
#     env["BACKEND_BASE_URL"] = "http://127.0.0.1:8001"
#     env["RABBITMQ_USER"] = "test"
#     env["RABBITMQ_PASSWORD"] = "test"
# 
#     # IMPORTANT: your backend expects IMAGES_DIR relative to cwd ("images") OR absolute.
#     # We run with cwd=backend/ and point IMAGES_DIR to that temp dir.
#     env["IMAGES_DIR"] = str(images_dir)
# 
#     # start backend (no uv, just your venv python)
#     cmd = [sys.executable, "-m", "uvicorn", "simple_social_backend.api:app", "--host", "127.0.0.1", "--port", "8001"]
#     env["PYTHONUNBUFFERED"] = "1"
#     p = subprocess.Popen(cmd, cwd=str(backend_dir), env=env)
# 
# 
#     try:
#         _wait_http("http://127.0.0.1:8001/posts", timeout_s=120)
#         yield {"base": "http://127.0.0.1:8001", "images_dir": str(images_dir), "proc": p}
#     finally:
#         p.terminate()
#         try:
#             p.wait(timeout=10)
#         except subprocess.TimeoutExpired:
#             p.kill()
#             p.wait(timeout=5)
# 
#         wal = Path(str(db_file) + "-wal")
#         shm = Path(str(db_file) + "-shm")
# 
#         # DB cleanup
#         for f in [db_file, wal, shm]:
#             for _ in range(30):
#                 try:
#                     f.unlink()
#                     break
#                 except FileNotFoundError:
#                     break
#                 except PermissionError:
#                     time.sleep(0.1)
# 
#         # images cleanup
#         for _ in range(30):
#             try:
#                 shutil.rmtree(images_dir)
#                 break
#             except FileNotFoundError:
#                 break
#             except PermissionError:
#                 time.sleep(0.1)


@pytest.fixture
def resizer_process(backend_server, rabbitmq):
    """
    Starts the resizer worker as a subprocess.
    If it exits immediately -> fail with its logs.
    """
    E2E_EXTERNAL = os.getenv("E2E_EXTERNAL") == "1"
    if E2E_EXTERNAL:
        yield None
        return
    repo_root = Path(__file__).resolve().parents[2]

    env = os.environ.copy()
    # env["RABBITMQ_HOST"] = rabbitmq["host"]
    env["RABBITMQ_HOST"] = "127.0.0.1"
    env["IMAGE_RESIZE_QUEUE"] = env.get("IMAGE_RESIZE_QUEUE", "image_resize")
    env["BACKEND_BASE_URL"] = backend_server["base"]
    env["IMAGES_DIR"] = backend_server["images_dir"]  # MUST match backend
    env["PYTHONUNBUFFERED"] = "1"
    env["RABBITMQ_USER"] = "test"
    env["RABBITMQ_PASSWORD"] = "test"


    # default: use console-script
    # (if your entrypoint differs, change this one line)
    cmd = ["social-resizer"]

    p = subprocess.Popen(cmd, cwd=str(repo_root), env=env)

    # give it a moment; if it dies -> show output and fail
    time.sleep(1.0)
    if p.poll() is not None:
        out = ""
        try:
            out = p.stdout.read() if p.stdout else ""
        except Exception:
            pass
        raise RuntimeError(f"Resizer exited immediately.\n--- output ---\n{out}\n--------------")

    try:
        yield p
    finally:
        p.terminate()
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait(timeout=5)

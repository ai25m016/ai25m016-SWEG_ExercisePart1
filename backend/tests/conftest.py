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
        base = os.getenv("BACKEND_BASE_URL", "http://127.0.0.1:8000")
        _wait_http(f"{base}/posts", timeout_s=120)

        images_dir = tmp_path / "images"
        (images_dir / "original").mkdir(parents=True, exist_ok=True)
        (images_dir / "thumbs").mkdir(parents=True, exist_ok=True)

        try:
            yield {"base": base, "images_dir": str(images_dir), "proc": None}
        finally:
            for _ in range(30):
                try:
                    shutil.rmtree(images_dir)
                    break
                except FileNotFoundError:
                    break
                except PermissionError:
                    time.sleep(0.1)
        return

    # --- INTERNAL BACKEND SETUP ---
    repo_root = Path(__file__).resolve().parents[2]
    backend_dir = repo_root / "backend"

    images_dir = tmp_path / "images"
    (images_dir / "original").mkdir(parents=True, exist_ok=True)
    (images_dir / "thumbs").mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    
    # Enable the queue logic
    if "DISABLE_QUEUE" in env:
        del env["DISABLE_QUEUE"]

    db_file = tmp_path / "test_social.db"
    env["DB_PATH"] = str(db_file)
    
    # ---------------------------------------------------------
    # CLEAN NETWORK CONFIGURATION (Matching Resizer)
    # ---------------------------------------------------------
    # 1. Force Host to 127.0.0.1 (IPv4)
    env["RABBITMQ_HOST"] = "127.0.0.1"
    
    # 2. Dynamic Port (from fixture)
    rmq_port = rabbitmq.get("port", rabbitmq.get("amqp_port", "5672"))
    env["RABBITMQ_PORT"] = str(rmq_port)

    # 3. Dynamic User/Pass (from fixture, usually 'test'/'test')
    env["RABBITMQ_USER"] = rabbitmq.get("user", rabbitmq.get("username", "test"))
    env["RABBITMQ_PASSWORD"] = rabbitmq.get("password", "test")

    # 4. REMOVE URL variables to prevent conflicts/formatting errors
    # We rely on the app reading the HOST/PORT/USER/PASS variables above.
    if "RABBITMQ_URL" in env:
        del env["RABBITMQ_URL"]
    if "BROKER_URL" in env:
        del env["BROKER_URL"]
        
    env["IMAGE_RESIZE_QUEUE"] = env.get("IMAGE_RESIZE_QUEUE", "image_resize")
    env["BACKEND_BASE_URL"] = "http://127.0.0.1:8001"
    env["IMAGES_DIR"] = str(images_dir)

    # Debug print
    print(f"DEBUG: Backend Starting -> Host: {env['RABBITMQ_HOST']}, Port: {env['RABBITMQ_PORT']}, User: {env['RABBITMQ_USER']}")

    # Start backend
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
        
        # Images cleanup
        for _ in range(30):
            try:
                shutil.rmtree(images_dir)
                break
            except FileNotFoundError:
                break
            except PermissionError:
                time.sleep(0.1)

@pytest.fixture
def resizer_process(backend_server, rabbitmq):
    """
    Starts the resizer worker as a subprocess.
    If it exits immediately -> fail.
    """
    E2E_EXTERNAL = os.getenv("E2E_EXTERNAL") == "1"
    if E2E_EXTERNAL:
        yield None
        return
    repo_root = Path(__file__).resolve().parents[2]

    env = os.environ.copy()
    
    # --- Sync settings with Backend ---
    env["RABBITMQ_HOST"] = "127.0.0.1"
    
    # Get Port/User/Pass from fixture
    rmq_port = rabbitmq.get("port", rabbitmq.get("amqp_port", "5672"))
    env["RABBITMQ_PORT"] = str(rmq_port)
    env["RABBITMQ_USER"] = rabbitmq.get("user", rabbitmq.get("username", "test"))
    env["RABBITMQ_PASSWORD"] = rabbitmq.get("password", "test")
    
    env["IMAGE_RESIZE_QUEUE"] = env.get("IMAGE_RESIZE_QUEUE", "image_resize")
    env["BACKEND_BASE_URL"] = backend_server["base"]
    env["IMAGES_DIR"] = backend_server["images_dir"]
    env["PYTHONUNBUFFERED"] = "1"

    print(f"DEBUG: Resizer Config -> Host: {env['RABBITMQ_HOST']}, Port: {env['RABBITMQ_PORT']}, User: {env['RABBITMQ_USER']}")

    cmd = ["social-resizer"]

    # --- FIX: REMOVE 'stdout=PIPE' so logs appear in console ---
    p = subprocess.Popen(cmd, cwd=str(repo_root), env=env)

    # Check if it dies immediately
    time.sleep(1.5)
    if p.poll() is not None:
        raise RuntimeError("Resizer exited immediately. Check the console logs above for the error!")

    try:
        yield p
    finally:
        p.terminate()
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait(timeout=5)

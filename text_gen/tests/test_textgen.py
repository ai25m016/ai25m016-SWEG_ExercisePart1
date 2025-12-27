# backend/tests/test_textgen.py
import pytest
from sqlalchemy import delete
from sqlmodel import Session
from fastapi.testclient import TestClient

from simple_social_backend.db import get_engine
from simple_social_backend.models import TextGenJob


pytestmark = pytest.mark.textgen  # wie die anderen api-tests


def _clear_textgen_jobs() -> None:
    with Session(get_engine()) as session:
        session.exec(delete(TextGenJob))
        session.commit()


def _latest_job_by_prompt(prompt: str) -> TextGenJob | None:
    from sqlmodel import select

    with Session(get_engine()) as session:
        return session.exec(
            select(TextGenJob)
            .where(TextGenJob.prompt == prompt)
            .order_by(TextGenJob.id.desc())
        ).first()


def test_textgen_job_is_created_and_can_be_updated(client, monkeypatch):
    """
    Verifiziert:
    - POST /textgen/jobs legt Job an (status=pending)
    - publish_textgen_job wird aufgerufen (stub, kein RabbitMQ nötig)
    - GET /textgen/jobs/{id} liefert Job
    - PUT /textgen/jobs/{id} updated status/generated_text/error
    """
    _clear_textgen_jobs()

    # --- stub publish_textgen_job, damit kein RabbitMQ gebraucht wird ---
    calls = {}

    def fake_publish_textgen_job(job_id: int, prompt: str, max_new_tokens: int = 60) -> None:
        calls["job_id"] = job_id
        calls["prompt"] = prompt
        calls["max_new_tokens"] = max_new_tokens

    import simple_social_backend.main as api
    monkeypatch.setattr(api, "publish_textgen_job", fake_publish_textgen_job, raising=True)

    # --- 1) Create job ---
    payload = {"prompt": "Hello from test", "max_new_tokens": 12}
    r = client.post("/textgen/jobs", json=payload)
    assert r.status_code == 200, r.text

    job = r.json()
    assert "id" in job
    assert job["prompt"] == payload["prompt"]
    assert job["status"] == "pending"
    assert job["max_new_tokens"] == payload["max_new_tokens"]
    assert job.get("generated_text") in (None, "")
    assert job.get("error") in (None, "")

    # publish was called
    assert calls["job_id"] == job["id"]
    assert calls["prompt"] == payload["prompt"]
    assert calls["max_new_tokens"] == payload["max_new_tokens"]

    # --- 2) Read job ---
    r = client.get(f"/textgen/jobs/{job['id']}")
    assert r.status_code == 200, r.text
    job2 = r.json()
    assert job2["id"] == job["id"]
    assert job2["status"] == "pending"

    # --- 3) Update job (simulate ml-worker result) ---
    upd = {"status": "done", "generated_text": "some generated text", "error": None}
    r = client.put(f"/textgen/jobs/{job['id']}", json=upd)
    assert r.status_code == 200, r.text

    job3 = r.json()
    assert job3["status"] == "done"
    assert job3["generated_text"] == "some generated text"
    assert job3["error"] is None

    # --- 4) Read again ---
    r = client.get(f"/textgen/jobs/{job['id']}")
    assert r.status_code == 200, r.text
    job4 = r.json()
    assert job4["status"] == "done"
    assert job4["generated_text"] == "some generated text"
    assert job4["error"] is None


def test_textgen_publish_failure_marks_job_error(monkeypatch):
    """
    Robustness:
    - publish_textgen_job crasht (RabbitMQ down)
    - API call liefert 5xx (weil Exception hochgeht)
    - ABER: Job wird trotzdem in DB als status=error markiert
    """
    _clear_textgen_jobs()

    def boom(*args, **kwargs):
        raise RuntimeError("rabbitmq down")

    import simple_social_backend.main as api
    monkeypatch.setattr(api, "publish_textgen_job", boom, raising=True)

    # wichtig: exceptions als HTTP 500 bekommen, nicht re-raise
    tc = TestClient(api.app, raise_server_exceptions=False)

    payload = {"prompt": "this will fail", "max_new_tokens": 5}
    r = tc.post("/textgen/jobs", json=payload)

    assert r.status_code >= 500, r.text

    job = _latest_job_by_prompt(payload["prompt"])
    assert job is not None
    assert job.status == "error"
    # optional, aber nice:
    assert job.error is None or len(str(job.error)) > 0

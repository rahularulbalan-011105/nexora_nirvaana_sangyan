"""Batch Analysis: creating a job, processing it through the engine, ownership and validation."""
from __future__ import annotations

import pytest

from tests.conftest import csrf_of
from tests.test_check import PLAIN, PNG, SCAM, make_pdf


@pytest.fixture
def sync_jobs(monkeypatch):
    """Run enqueued jobs inline so the test sees the finished batch."""
    from app.services import jobs

    calls: list[tuple] = []

    def run_now(target, *args):
        calls.append((target, args))
        jobs.resolve(target)(*args)
        return "inline"

    monkeypatch.setattr(jobs, "enqueue", run_now)
    return calls


@pytest.fixture
def user_client(auth_client, request):
    return auth_client(email=f"batch-{request.node.name[:40]}@test.local")


def post(client, data=None, files=None):
    return client.post(
        "/api/batch",
        data=data or {},
        files=files,
        headers={"X-CSRF-Token": csrf_of(client), "Accept": "application/json"},
    )


def test_create_and_process_batch(user_client, sync_jobs, db, monkeypatch):
    from app.services import analysis_inputs as inputs

    monkeypatch.setattr(inputs, "ocr_available", lambda: False)
    from app.models.analysis import BatchItem, BatchJob, MessageAnalysis

    files = [
        ("files", ("offer.pdf", make_pdf("Guaranteed returns with zero risk. Pay today."), "application/pdf")),
        ("files", ("shot.png", PNG, "image/png")),
    ]
    r = post(
        user_client,
        data={
            "label": "Family forwards",
            "messages": SCAM + "\n---\n" + PLAIN,
            "links": "https://bit.ly/abc",
            "file_texts": ["", "Urgent! Send your OTP 123456 now to claim the prize."],
        },
        files=files,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 5
    assert sync_jobs and sync_jobs[0][0] == "app.services.batch:process_job"

    status = user_client.get(f"/api/batch/{body['id']}").json()
    assert status["status"] == "COMPLETED"
    assert status["running"] is False
    assert status["total"] == 5 and status["completed"] == 5 and status["failed"] == 0
    assert status["progress"] == 100
    assert sum(status["counts"][k] for k in ("clean", "verify", "multiple")) == 5
    assert status["counts"]["clean"] >= 1  # the society-meeting message
    assert all(i["result_status"] for i in status["items"])
    assert "Batch Analysis Results" in status["html"]

    db.expire_all()
    job = db.get(BatchJob, __import__("uuid").UUID(body["id"]))
    assert job.label == "Family forwards"
    assert job.finished_at is not None
    assert "pending" not in (job.summary or {})  # prepared text is dropped once done
    assert sum(job.summary["by_status"].values()) == 5
    items = db.query(BatchItem).filter(BatchItem.job_id == job.id).all()
    for item in items:
        analysis = db.get(MessageAnalysis, item.analysis_id)
        assert analysis is not None and analysis.batch_item_id == item.id
        assert analysis.status == item.result_status
        assert "123456" not in (analysis.raw_text or "")  # OTP masked
    image = next(i for i in items if i.display_name == "shot.png")
    assert image.uploaded_file_id is not None

    # Re-running a finished job is a no-op (safe to retry).
    from app.services.batch import process_job

    before = db.query(MessageAnalysis).filter(MessageAnalysis.user_id == job.user_id).count()
    process_job(str(job.id))
    db.expire_all()
    assert db.query(MessageAnalysis).filter(MessageAnalysis.user_id == job.user_id).count() == before

    # Exports and journal work for the finished job.
    assert user_client.get(f"/reports/batch/{job.id}").status_code == 200
    csv = user_client.get(f"/reports/batch/{job.id}.csv")
    assert csv.status_code == 200 and "shot.png" in csv.text
    saved = user_client.post(
        f"/api/batch/{job.id}/journal", headers={"X-CSRF-Token": csrf_of(user_client)}
    )
    assert saved.status_code == 200 and saved.json()["saved"] is True

    page = user_client.get("/batch")
    assert page.status_code == 200
    assert "Family forwards" in page.text and "batch.js" in page.text


def test_failed_item_does_not_abort_job(user_client, sync_jobs, db, monkeypatch):
    from app.services import analysis as engine

    real = engine.analyse

    def flaky(db_, user, data, **kw):
        if "BOOM" in (data.text or ""):
            raise RuntimeError("engine fault")
        return real(db_, user, data, **kw)

    monkeypatch.setattr(engine, "analyse", flaky)
    r = post(user_client, data={"messages": "BOOM\n---\n" + PLAIN})
    assert r.status_code == 200, r.text
    status = user_client.get(f"/api/batch/{r.json()['id']}").json()
    assert status["status"] == "COMPLETED"
    assert status["completed"] == 1 and status["failed"] == 1
    failed = next(i for i in status["items"] if i["status"] == "FAILED")
    assert failed["error"] and failed["result_status"] is None


def test_batch_is_private_to_its_owner(auth_client, sync_jobs):
    owner = auth_client(email="batch-owner@test.local")
    job_id = post(owner, data={"messages": PLAIN}).json()["id"]
    owner.cookies.clear()

    other = auth_client(email="batch-other@test.local")
    assert other.get(f"/api/batch/{job_id}").status_code == 404
    assert other.get("/api/batch/not-a-uuid").status_code == 404
    r = other.post(f"/api/batch/{job_id}/journal", headers={"X-CSRF-Token": csrf_of(other)})
    assert r.status_code == 404
    assert other.get(f"/reports/batch/{job_id}").status_code == 404


def test_requires_login_and_csrf(client, user_client, sync_jobs):
    r = user_client.post("/api/batch", data={"messages": PLAIN}, headers={"Accept": "application/json"})
    assert r.status_code in (400, 403)


@pytest.mark.parametrize(
    "data,files,code",
    [
        ({"messages": "  \n---\n  ", "links": ""}, None, "empty"),
        ({"messages": "\n---\n".join(f"Message {i}" for i in range(21))}, None, "too_many"),
        ({"messages": "x" * 10_001}, None, "too_long"),
        ({"links": "not a link"}, None, "bad_url"),
        ({}, [("files", ("notes.txt", b"just some text", "text/plain"))], "bad_file"),
        ({}, [("files", ("shot.png", PNG, "image/png"))], "need_typed"),
        ({}, [("files", ("scan.pdf", make_pdf(None), "application/pdf"))], "pdf_no_text"),
    ],
)
def test_validation(user_client, sync_jobs, data, files, code, monkeypatch):
    from app.services import analysis_inputs as inputs

    monkeypatch.setattr(inputs, "ocr_available", lambda: False)
    r = post(user_client, data=data, files=files)
    assert r.status_code == 422, r.text
    assert r.json()["code"] == code
    assert not sync_jobs  # nothing was queued


def test_file_too_large(user_client, sync_jobs, monkeypatch):
    from app.services import analysis_inputs as inputs

    monkeypatch.setattr(inputs, "max_bytes", lambda: 100)
    r = post(user_client, data={}, files=[("files", ("big.pdf", make_pdf("hello " * 50), "application/pdf"))])
    assert r.status_code == 422 and r.json()["code"] == "bad_file"
    assert "larger" in r.json()["detail"]


def test_too_many_mixed_items(user_client, sync_jobs):
    files = [("files", (f"f{i}.pdf", make_pdf("Hello"), "application/pdf")) for i in range(5)]
    r = post(
        user_client,
        data={"messages": "\n---\n".join(f"Message {i}" for i in range(10)),
              "links": "\n".join(f"https://example{i}.com" for i in range(6))},
        files=files,
    )
    assert r.status_code == 422 and r.json()["code"] == "too_many"


def test_respects_history_opt_out(user_client, sync_jobs, db):
    import uuid

    from app.models.analysis import BatchItem, BatchJob
    from app.models.user import User
    from app.services import account

    user = db.query(User).filter(User.email == "batch-test_respects_history_opt_out@test.local").one()
    account.update_privacy(db, user, {"store_analysis_history": False})
    db.commit()

    r = post(user_client, data={"messages": SCAM})
    assert r.status_code == 200, r.text
    db.expire_all()
    job = db.get(BatchJob, uuid.UUID(r.json()["id"]))
    item = db.query(BatchItem).filter(BatchItem.job_id == job.id).one()
    assert item.analysis_id is None
    assert item.result_status is not None
    assert item.display_name == "Message 1"  # no content kept in the item name
    assert "pending" not in (job.summary or {})

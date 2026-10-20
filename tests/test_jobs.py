"""Tests for background jobs and the /api/jobs endpoints."""

import io
import threading
import time

from asl_util.jobs import JobFailed, JobRunner

from conftest import FakeTranscriber


def wait_for(get_status, until=("done", "error"), timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        status = get_status()
        if status["status"] in until:
            return status
        time.sleep(0.01)
    raise AssertionError(f"job still {status['status']}")


def test_job_reports_progress_and_result():
    runner = JobRunner()
    gate = threading.Event()

    def process(report):
        report("animating", 2, 5)
        gate.wait(2)
        return {"answer": 42}

    job_id = runner.submit(process)
    status = wait_for(lambda: runner.status(job_id), until=("animating",))
    assert (status["done"], status["total"]) == (2, 5)
    gate.set()
    status = wait_for(lambda: runner.status(job_id))
    assert status["status"] == "done" and status["result"] == {"answer": 42}


def test_jobs_run_one_at_a_time_and_report_their_place_in_line():
    runner = JobRunner()
    gate = threading.Event()
    first = runner.submit(lambda report: gate.wait(2) or {})
    second = runner.submit(lambda report: {})
    wait_for(lambda: runner.status(first), until=("queued",))
    assert runner.status(second)["status"] == "queued"
    assert runner.status(second)["ahead"] == 1
    gate.set()
    assert wait_for(lambda: runner.status(second))["status"] == "done"


def test_failed_job_shows_safe_message_and_still_cleans_up():
    runner = JobRunner()
    cleaned = []

    def boom(report):
        raise RuntimeError("secret internal detail")

    def expected(report):
        raise JobFailed("No speech was found in this file.")

    a = runner.submit(boom, cleanup=lambda: cleaned.append("a"))
    b = runner.submit(expected, cleanup=lambda: cleaned.append("b"))
    assert "secret" not in wait_for(lambda: runner.status(a))["error"]
    assert wait_for(lambda: runner.status(b))["error"] == "No speech was found in this file."
    assert cleaned == ["a", "b"]


def test_unknown_job_is_none():
    assert JobRunner().status("nope") is None


def start(client, name="talk.mp4"):
    return client.post("/api/jobs", data={"file": (io.BytesIO(b"fake"), name)}, content_type="multipart/form-data")


def test_api_job_runs_to_the_same_result_as_upload(client, upload_dir):
    res = start(client)
    assert res.status_code == 202
    job_id = res.get_json()["id"]
    status = wait_for(lambda: client.get(f"/api/jobs/{job_id}").get_json())
    assert status["status"] == "done"
    assert status["result"]["result"] == "hello aadi the cat is sleeping"
    assert status["stages"] == ["queued", "transcribing", "translating", "animating", "done"]
    assert not list((upload_dir / "signmeup").iterdir())  # upload deleted after processing


def test_api_job_rejects_bad_uploads_immediately(client):
    assert start(client, "notes.txt").status_code == 415
    assert client.post("/api/jobs").status_code == 400


def test_api_job_without_speech_ends_with_error(transcriber, client):
    transcriber.segments = []
    job_id = start(client).get_json()["id"]
    status = wait_for(lambda: client.get(f"/api/jobs/{job_id}").get_json())
    assert status["status"] == "error" and status["error"] == "No speech was found in this file."


def test_api_unknown_job_is_404(client):
    res = client.get("/api/jobs/does-not-exist")
    assert res.status_code == 404 and "error" in res.get_json()

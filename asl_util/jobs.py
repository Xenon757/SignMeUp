"""Background processing of uploads, with progress the page can poll.

Turning a video into signs takes from a few seconds to a minute (transcribing,
translating, then making any sign animations not made before). Instead of one
long request, an upload becomes a job: it runs in the background and the page
asks for its status, so it can show what is actually happening.

Jobs run one at a time, in upload order: the speech and parsing models are
shared and not safe to use from several threads at once.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

log = logging.getLogger(__name__)

# Stages, in order. The page shows each one as waiting, running or done.
STAGES = ("queued", "transcribing", "translating", "animating", "done")

Report = Callable[..., None]           # report(stage, done=None, total=None)
Process = Callable[[Report], dict]     # runs a job, reporting progress; returns its result


class JobFailed(Exception):
    """A job error whose message is safe to show the user."""


@dataclass
class Job:
    id: str
    status: str = "queued"
    done: Optional[int] = None
    total: Optional[int] = None
    result: Optional[dict] = None
    error: Optional[str] = None
    created: float = field(default_factory=time.time)


class JobRunner:
    """Runs jobs one at a time in a background thread and keeps their status.

    Finished jobs are forgotten after `keep_seconds`.
    """

    def __init__(self, keep_seconds: float = 3600):
        self._jobs: Dict[str, Job] = {}
        self._order: List[str] = []
        self._lock = threading.Lock()
        self._worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="signmeup-job")
        self._keep = keep_seconds

    def submit(self, process: Process, cleanup: Optional[Callable[[], None]] = None) -> str:
        job = Job(id=uuid.uuid4().hex)
        with self._lock:
            self._forget_old()
            self._jobs[job.id] = job
            self._order.append(job.id)
        self._worker.submit(self._run, job, process, cleanup)
        return job.id

    def status(self, job_id: str) -> Optional[dict]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            out = {"id": job.id, "status": job.status, "stages": list(STAGES)}
            if job.done is not None:
                out.update(done=job.done, total=job.total)
            if job.status == "queued":
                ahead = [j for j in self._order if j != job.id and self._jobs[j].status not in ("done", "error")]
                out["ahead"] = len(ahead[: self._order.index(job.id)])
            if job.result is not None:
                out["result"] = job.result
            if job.error is not None:
                out["error"] = job.error
            return out

    def _run(self, job: Job, process: Process, cleanup: Optional[Callable[[], None]]) -> None:
        def report(stage: str, done: Optional[int] = None, total: Optional[int] = None) -> None:
            with self._lock:
                job.status, job.done, job.total = stage, done, total

        try:
            result = process(report)
            with self._lock:
                job.status, job.result, job.done, job.total = "done", result, None, None
        except JobFailed as exc:
            with self._lock:
                job.status, job.error = "error", str(exc)
        except Exception:
            log.exception("Job %s failed", job.id)
            with self._lock:
                job.status, job.error = "error", "Something went wrong while processing the video. Please try again."
        finally:
            if cleanup:
                cleanup()

    def _forget_old(self) -> None:
        cutoff = time.time() - self._keep
        for job_id in [j for j in self._order if self._jobs[j].created < cutoff and self._jobs[j].status in ("done", "error")]:
            self._order.remove(job_id)
            del self._jobs[job_id]

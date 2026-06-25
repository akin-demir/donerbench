from __future__ import annotations

import logging
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from donerbench.benchmark import run_benchmark
from donerbench.schemas import BenchmarkJobStart, BenchmarkJobStatus, BenchmarkRequest, BenchmarkResult


logger = logging.getLogger("donerbench.jobs")


@dataclass
class JobState:
    job_id: str
    request: BenchmarkRequest
    status: str = "queued"
    progress: float = 0.0
    message: str = "Queued"
    partial_result: BenchmarkResult | None = None
    result: BenchmarkResult | None = None
    error: str | None = None


class BenchmarkJobManager:
    def __init__(self) -> None:
        self._executor = ThreadPoolExecutor(max_workers=2)
        self._jobs: dict[str, JobState] = {}
        self._lock = threading.Lock()

    def start(self, request: BenchmarkRequest) -> BenchmarkJobStart:
        job_id = uuid.uuid4().hex
        state = JobState(job_id=job_id, request=request)
        with self._lock:
            self._jobs[job_id] = state
        self._executor.submit(self._run, job_id)
        return BenchmarkJobStart(job_id=job_id, status="queued")

    def status(self, job_id: str) -> BenchmarkJobStatus | None:
        with self._lock:
            state = self._jobs.get(job_id)
            if not state:
                return None
            return BenchmarkJobStatus(
                job_id=state.job_id,
                status=state.status,  # type: ignore[arg-type]
                progress=state.progress,
                message=state.message,
                partial_result=state.partial_result,
                result=state.result,
                error=state.error,
            )

    def _run(self, job_id: str) -> None:
        state = self._get(job_id)
        if not state:
            return
        self._update(job_id, status="running", progress=0.02, message="Starting agents")
        try:
            result = run_benchmark(
                state.request,
                progress_callback=lambda progress, message: self._update(
                    job_id,
                    status="running",
                    progress=progress,
                    message=message,
                ),
                partial_callback=lambda partial_result, progress, message: self._update(
                    job_id,
                    status="running",
                    progress=progress,
                    message=message,
                    partial_result=partial_result,
                ),
            )
            self._update(
                job_id,
                status="complete",
                progress=1.0,
                message="Benchmark complete",
                result=result,
            )
        except Exception as exc:
            logger.exception("Benchmark job failed job_id=%s", job_id)
            self._update(
                job_id,
                status="failed",
                progress=1.0,
                message="Benchmark failed",
                error=str(exc),
            )

    def _get(self, job_id: str) -> JobState | None:
        with self._lock:
            return self._jobs.get(job_id)

    def _update(
        self,
        job_id: str,
        *,
        status: str | None = None,
        progress: float | None = None,
        message: str | None = None,
        partial_result: BenchmarkResult | None = None,
        result: BenchmarkResult | None = None,
        error: str | None = None,
    ) -> None:
        with self._lock:
            state = self._jobs.get(job_id)
            if not state:
                return
            if status is not None:
                state.status = status
            if progress is not None:
                state.progress = max(state.progress, max(0.0, min(1.0, progress)))
            if message is not None:
                state.message = message
            if partial_result is not None:
                state.partial_result = partial_result
            if result is not None:
                state.result = result
                state.partial_result = result
            if error is not None:
                state.error = error


job_manager = BenchmarkJobManager()

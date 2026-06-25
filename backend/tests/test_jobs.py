from donerbench.benchmark.jobs import BenchmarkJobManager
from donerbench.schemas import BenchmarkRequest
import time


def test_job_manager_runs_benchmark_in_background(monkeypatch) -> None:
    monkeypatch.setenv("DONERBENCH_AGENT_MODE", "profile")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic")
    manager = BenchmarkJobManager()

    started = manager.start(
        BenchmarkRequest(agent_ids=["gpt-5.5"], slice_attempts=6, ticks_per_second=2)
    )

    for _ in range(100):
        status = manager.status(started.job_id)
        assert status is not None
        if status.status == "complete":
            break
        time.sleep(0.01)
    else:
        raise AssertionError("benchmark job did not complete")

    assert status.result is not None
    assert status.progress == 1.0

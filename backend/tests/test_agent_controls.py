from donerbench.agents import build_agent
from donerbench.schemas import BenchmarkRequest
from donerbench.benchmark import run_benchmark


def test_agent_action_controls_heat_and_rotation(monkeypatch) -> None:
    monkeypatch.setenv("DONERBENCH_AGENT_MODE", "profile")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai")

    agent = build_agent("gpt-5.5", seed=1)
    result = run_benchmark(
        BenchmarkRequest(agent_ids=[agent.id], slice_attempts=12, ticks_per_second=5)
    )
    frames = result.runs[0].frames

    rotation_values = {frame.doner_rotation_speed for frame in frames}
    heat_values = {frame.heat_temperature for frame in frames}

    assert len(rotation_values) > 1
    assert len(heat_values) > 1
    assert all(0.2 <= frame.doner_rotation_speed <= 3.0 for frame in frames)
    assert all(120.0 <= frame.heat_temperature <= 260.0 for frame in frames)

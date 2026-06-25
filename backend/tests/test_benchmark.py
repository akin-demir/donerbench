from donerbench.benchmark import run_benchmark
from donerbench.agents.base import Agent
from donerbench.schemas import AgentAction, BenchmarkRequest, Observation


class StartProbeAgent(Agent):
    description = "Test agent that records start order."
    starts: list[str] = []

    def __init__(self, agent_id: str, seed: int) -> None:
        super().__init__(seed=seed)
        self.id = agent_id
        self.name = agent_id
        self.started = False

    def act(self, observation: Observation) -> AgentAction:
        if not self.started:
            self.started = True
            self.starts.append(self.id)
        return AgentAction(
            doner_rotation_speed=0.8,
            heat_temperature=185.0,
            knife_angle=12.0,
            knife_velocity=0.5,
            inward_pressure=0.45,
            vibration_frequency=30.0,
            vibration_amplitude=0.3,
            cut_location_from_top=0.45,
            cut_depth=0.5,
        )


def test_benchmark_is_deterministic_for_same_seed(monkeypatch) -> None:
    monkeypatch.setenv("DONERBENCH_AGENT_MODE", "profile")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic")
    monkeypatch.setenv("LOCAL_LLM_QWEN_BASE_URL", "http://localhost:9001/v1")
    request = BenchmarkRequest(
        agent_ids=["gpt-5.5", "claude-sonnet-4.6", "qwen3.6"],
        seed=123,
        slice_attempts=12,
        ticks_per_second=5,
    )

    first = run_benchmark(request)
    second = run_benchmark(request)

    assert first.model_dump() == second.model_dump()


def test_scores_are_normalized(monkeypatch) -> None:
    monkeypatch.setenv("DONERBENCH_AGENT_MODE", "profile")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic")
    result = run_benchmark(
        BenchmarkRequest(agent_ids=["gpt-5.5", "claude-opus-4.6"], slice_attempts=10, ticks_per_second=5)
    )

    assert len(result.leaderboard) == 2
    for run in result.runs:
        assert 0 <= run.final_score <= 100
        assert run.slices
        assert run.frames


def test_leaderboard_is_ranked_descending(monkeypatch) -> None:
    monkeypatch.setenv("DONERBENCH_AGENT_MODE", "profile")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic")
    monkeypatch.setenv("LOCAL_LLM_QWEN_BASE_URL", "http://localhost:9001/v1")
    result = run_benchmark(
        BenchmarkRequest(agent_ids=["gpt-5.5", "claude-sonnet-4.6", "qwen3.6"], slice_attempts=10)
    )

    scores = [entry.final_score for entry in result.leaderboard]
    assert scores == sorted(scores, reverse=True)


def test_benchmark_streams_partial_results(monkeypatch) -> None:
    monkeypatch.setenv("DONERBENCH_AGENT_MODE", "profile")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai")
    updates = []

    result = run_benchmark(
        BenchmarkRequest(agent_ids=["gpt-5.5"], slice_attempts=6, ticks_per_second=2),
        partial_callback=lambda partial, progress, message: updates.append((partial, progress, message)),
    )

    assert result.status == "complete"
    assert updates
    first_partial, first_progress, first_message = updates[0]
    assert first_partial.status == "running"
    assert first_partial.runs[0].frames
    assert 0 < first_progress <= 1
    assert first_partial.runs[0].frames[0].agent_trace["mode"] == "waiting"
    assert "Waiting" in first_message
    assert any("attempt" in message for _, _, message in updates)


def test_benchmark_starts_selected_agents_in_parallel(monkeypatch) -> None:
    import donerbench.benchmark.runner as runner

    StartProbeAgent.starts = []

    def fake_build_agent(agent_id: str, seed: int) -> StartProbeAgent:
        return StartProbeAgent(agent_id=agent_id, seed=seed)

    monkeypatch.setattr(runner, "build_agent", fake_build_agent)

    result = run_benchmark(
        BenchmarkRequest(agent_ids=["agent-a", "agent-b", "agent-c"], slice_attempts=6, ticks_per_second=2)
    )

    assert [run.agent_id for run in result.runs] == ["agent-a", "agent-b", "agent-c"]
    assert set(StartProbeAgent.starts) == {"agent-a", "agent-b", "agent-c"}

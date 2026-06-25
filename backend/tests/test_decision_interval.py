from donerbench.agents.base import Agent
from donerbench.benchmark import run_benchmark
from donerbench.schemas import AgentAction, BenchmarkRequest, EnvironmentConfig, Observation
from donerbench.simulation import SimulationEngine


def _action() -> AgentAction:
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


class CountingAgent(Agent):
    id = "counting"
    name = "Counting"
    description = "Counts how many times it is queried."

    def __init__(self, seed: int = 0) -> None:
        super().__init__(seed=seed)
        self.calls = 0

    def act(self, observation: Observation) -> AgentAction:
        self.calls += 1
        return _action()


class FlakyAgent(Agent):
    id = "flaky"
    name = "Flaky"
    description = "Raises on the third query."

    def __init__(self, seed: int = 0) -> None:
        super().__init__(seed=seed)
        self.calls = 0

    def act(self, observation: Observation) -> AgentAction:
        self.calls += 1
        if self.calls == 3:
            raise RuntimeError("boom")
        self.last_decision_trace = {"mode": "live"}
        return _action()


def test_agent_is_queried_once_per_attempt() -> None:
    engine = SimulationEngine(
        environment=EnvironmentConfig(),
        slice_attempts=15,
        ticks_per_second=10,
    )
    agent = CountingAgent()
    result = engine.run_agent(agent)

    # Exactly one model query per attempt, regardless of how many render frames run.
    assert agent.calls == 15
    assert len(result.frames) == 15 * engine.ticks_per_attempt
    assert sum(1 for frame in result.frames if frame.decision) == 15


def test_engine_holds_action_between_attempts() -> None:
    engine = SimulationEngine(
        environment=EnvironmentConfig(),
        slice_attempts=4,
        ticks_per_second=10,
    )
    result = engine.run_agent(CountingAgent())

    held = [frame for frame in result.frames if not frame.decision]
    assert held  # most frames reuse the committed action
    assert all(frame.agent_trace.get("mode") == "held" for frame in held)


def test_runner_isolates_a_raising_agent(monkeypatch) -> None:
    # A non-recoverable agent error degrades to an errored leaderboard entry
    # instead of failing the whole job.
    import donerbench.benchmark.runner as runner

    monkeypatch.setattr(runner, "build_agent", lambda agent_id, seed: FlakyAgent(seed=seed))
    result = run_benchmark(
        BenchmarkRequest(
            agent_ids=["flaky"],
            slice_attempts=6,
            ticks_per_second=2,
        )
    )

    assert result.status == "complete"
    assert len(result.runs) == 1
    assert result.runs[0].verdict.startswith("Errored")

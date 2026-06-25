from donerbench.agents.base import Agent
from donerbench.schemas import AgentAction, BenchmarkRequest, Observation


class HistoryProbeAgent(Agent):
    id = "history-probe"
    name = "HistoryProbeAgent"
    description = "Test agent that records observation history lengths."

    def __init__(self, seed: int) -> None:
        super().__init__(seed)
        self.history_lengths: list[int] = []

    def act(self, observation: Observation) -> AgentAction:
        self.history_lengths.append(len(observation.action_history))
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


def test_agent_receives_full_attempt_history() -> None:
    agent = HistoryProbeAgent(seed=1)
    engine_request = BenchmarkRequest(agent_ids=["local-llm"], slice_attempts=6, ticks_per_second=5)

    # Use the engine through a direct import so we can inspect this test agent instance.
    from donerbench.simulation import SimulationEngine

    engine = SimulationEngine(
        environment=engine_request.environment,
        slice_attempts=engine_request.slice_attempts,
        ticks_per_second=engine_request.ticks_per_second,
        seed=engine_request.seed,
    )
    engine.run_agent(agent)

    # One query per attempt; each attempt sees every prior attempt (the N-1 steps).
    assert len(agent.history_lengths) == engine_request.slice_attempts
    assert agent.history_lengths == list(range(engine_request.slice_attempts))


def test_engine_emits_a_frame_for_every_tick() -> None:
    agent = HistoryProbeAgent(seed=1)
    engine_request = BenchmarkRequest(agent_ids=["local-llm"], slice_attempts=6, ticks_per_second=5)

    from donerbench.simulation import SimulationEngine

    engine = SimulationEngine(
        environment=engine_request.environment,
        slice_attempts=engine_request.slice_attempts,
        ticks_per_second=engine_request.ticks_per_second,
        seed=engine_request.seed,
    )
    updates = []
    engine.run_agent(
        agent,
        frame_callback=lambda frames, slices, live_score, tick, total_ticks: updates.append(
            (frames[-1], slices.copy(), live_score, tick, total_ticks)
        ),
    )

    expected_ticks = engine_request.slice_attempts * engine.ticks_per_attempt
    assert len(updates) == expected_ticks
    first_frame, _, _, first_tick, total_ticks = updates[0]
    assert first_tick == 0
    assert first_frame.decision is True
    assert total_ticks == expected_ticks

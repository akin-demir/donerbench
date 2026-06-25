from __future__ import annotations

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from statistics import mean, pvariance
from threading import Lock
from typing import Literal

from donerbench.agents import build_agent
from donerbench.schemas import (
    AgentRunResult,
    BenchmarkRequest,
    BenchmarkResult,
    KnifeState,
    LeaderboardEntry,
    SimulationFrame,
    SliceMetrics,
)
from donerbench.simulation import SimulationEngine


logger = logging.getLogger("donerbench.benchmark")

ProgressCallback = Callable[[float, str], None]
PartialCallback = Callable[[BenchmarkResult, float, str], None]


def _errored_run(agent, error: Exception) -> AgentRunResult:
    return AgentRunResult(
        agent_id=agent.id,
        agent_name=agent.name,
        final_score=0.0,
        component_scores={"live_score": 0.0},
        slices=[],
        frames=[],
        verdict=f"Errored: {error}"[:120],
    )


def run_benchmark(
    request: BenchmarkRequest,
    progress_callback: ProgressCallback | None = None,
    partial_callback: PartialCallback | None = None,
) -> BenchmarkResult:
    total_agents = max(1, len(request.agent_ids))
    agents = [
        (agent_id, build_agent(agent_id, request.seed + index * 997))
        for index, agent_id in enumerate(request.agent_ids)
    ]
    runs_by_index: list[AgentRunResult] = [
        _pending_run(agent, _initial_frame(request, agent_id=agent_id, agent=agent))
        for agent_id, agent in agents
    ]
    progress_by_index = [0.0 for _ in agents]
    lock = Lock()

    def emit(progress: float | None = None, message: str | None = None) -> None:
        with lock:
            snapshot = list(runs_by_index)
            total_progress = progress if progress is not None else sum(progress_by_index) / total_agents
        if partial_callback:
            partial_callback(
                _benchmark_result(
                    request=request,
                    runs=snapshot,
                    leaderboard=[],
                    status="running",
                ),
                total_progress,
                message or "Running agents",
            )
        if progress_callback:
            progress_callback(total_progress, message or "Running agents")

    if partial_callback:
        emit(progress=0.02, message="Waiting for first model commands")

    def run_one(index: int, agent_id: str, agent) -> AgentRunResult:
        engine = SimulationEngine(
            environment=request.environment,
            slice_attempts=request.slice_attempts,
            ticks_per_second=request.ticks_per_second,
            seed=request.seed,
        )
        ticks_per_attempt = engine.ticks_per_attempt
        total_attempts = request.slice_attempts

        def on_frame(
            frames,
            slices,
            live_score,
            tick,
            total_ticks,
            *,
            agent_id=agent.id,
            agent_name=agent.name,
            agent_index=index,
        ) -> None:
            agent_progress = (tick + 1) / max(1, total_ticks)
            attempt_no = tick // ticks_per_attempt + 1
            message = f"Running {agent_id}: attempt {attempt_no}/{total_attempts}"
            partial_run = AgentRunResult(
                agent_id=agent_id,
                agent_name=agent_name,
                final_score=round(live_score, 2),
                component_scores={"live_score": round(live_score, 2)},
                slices=slices,
                frames=frames,
                verdict="Running",
            )
            with lock:
                progress_by_index[agent_index] = agent_progress
                runs_by_index[agent_index] = partial_run
            emit(message=message)

        if progress_callback:
            progress_callback(sum(progress_by_index) / total_agents, f"Running {agent_id}")
        try:
            result = engine.run_agent(agent, frame_callback=on_frame)
        except Exception as exc:  # noqa: BLE001 - one agent failing must not abort the job
            logger.exception("Agent run failed agent=%s", agent_id)
            result = _errored_run(agent, exc)
        with lock:
            progress_by_index[index] = 1.0
            runs_by_index[index] = result
        emit(message=f"Finished {agent_id}")
        return result

    with ThreadPoolExecutor(max_workers=max(1, len(agents))) as executor:
        futures = [
            executor.submit(run_one, index, agent_id, agent)
            for index, (agent_id, agent) in enumerate(agents)
        ]
        for future in as_completed(futures):
            future.result()

    runs = list(runs_by_index)

    ranked_runs = sorted(runs, key=lambda run: run.final_score, reverse=True)
    leaderboard = [
        _leaderboard_entry(rank=index + 1, run=run)
        for index, run in enumerate(ranked_runs)
    ]
    return _benchmark_result(
        request=request,
        runs=runs,
        leaderboard=leaderboard,
        status="complete",
    )


def _benchmark_result(
    *,
    request: BenchmarkRequest,
    runs: list[AgentRunResult],
    leaderboard: list[LeaderboardEntry],
    status: Literal["running", "complete"],
) -> BenchmarkResult:
    return BenchmarkResult(
        seed=request.seed,
        slice_attempts=request.slice_attempts,
        ticks_per_second=request.ticks_per_second,
        environment=request.environment,
        status=status,
        runs=runs,
        leaderboard=leaderboard,
    )


def _pending_run(agent, frame: SimulationFrame) -> AgentRunResult:
    return AgentRunResult(
        agent_id=agent.id,
        agent_name=agent.name,
        final_score=0.0,
        component_scores={"live_score": 0.0},
        slices=[],
        frames=[frame],
        verdict="Waiting",
    )


def _initial_frame(request: BenchmarkRequest, *, agent_id: str, agent) -> SimulationFrame:
    return SimulationFrame(
        tick=0,
        time_seconds=0.0,
        rotation_angle=0.0,
        doner_rotation_speed=round(request.environment.doner_rotation_speed, 3),
        heat_temperature=round(request.environment.heat_temperature, 2),
        knife_state=KnifeState(),
        live_score=0.0,
        action_label="Waiting for model",
        agent_trace={
            "mode": "waiting",
            "agent_id": agent_id,
            "provider": getattr(agent, "provider", "unknown"),
            "model": getattr(agent, "model", agent_id),
        },
        latest_slice=None,
        cut_marks=[],
    )


def _leaderboard_entry(rank: int, run) -> LeaderboardEntry:
    slices: list[SliceMetrics] = run.slices
    valid_slices = [slice_ for slice_ in slices if slice_.valid]
    source = valid_slices or slices
    if not source:
        return LeaderboardEntry(
            rank=rank,
            agent_id=run.agent_id,
            agent_name=run.agent_name,
            final_score=run.final_score,
            valid_slice_count=0,
            average_thickness=0.0,
            thickness_variance=0.0,
            average_area=0.0,
            average_freshness=0.0,
            waste_percentage=0.0,
            tear_penalty=0.0,
            verdict=run.verdict,
        )

    thicknesses = [slice_.thickness_mm for slice_ in source]
    return LeaderboardEntry(
        rank=rank,
        agent_id=run.agent_id,
        agent_name=run.agent_name,
        final_score=run.final_score,
        valid_slice_count=len(valid_slices),
        average_thickness=round(mean(thicknesses), 2),
        thickness_variance=round(pvariance(thicknesses) if len(thicknesses) > 1 else 0.0, 3),
        average_area=round(mean(slice_.surface_area_cm2 for slice_ in source), 2),
        average_freshness=round(mean(slice_.freshness_score for slice_ in source), 2),
        waste_percentage=round(mean(slice_.waste_penalty for slice_ in source), 2),
        tear_penalty=round(mean(slice_.tear_penalty for slice_ in source), 2),
        verdict=run.verdict,
    )

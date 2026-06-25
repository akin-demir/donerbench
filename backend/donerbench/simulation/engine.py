from __future__ import annotations

import math
import random
from collections.abc import Callable
from statistics import pvariance

from donerbench.agents import Agent
from donerbench.schemas import (
    CUT_DEPTH_MAX_MM,
    INWARD_PRESSURE_MAX_N,
    KNIFE_VELOCITY_MAX_CM_S,
    VIBRATION_AMPLITUDE_MAX_MM,
    ActionResult,
    AgentRunResult,
    EnvironmentConfig,
    KnifeState,
    Observation,
    SimulationFrame,
    SliceMetrics,
)
from donerbench.scoring import score_run


FrameCallback = Callable[[list[SimulationFrame], list[SliceMetrics], float, int, int], None]


class SimulationEngine:
    def __init__(
        self,
        environment: EnvironmentConfig,
        slice_attempts: int = 30,
        ticks_per_second: int = 10,
        seed: int = 42,
        ticks_per_attempt: int = 8,
    ) -> None:
        self.environment = environment
        self.ticks_per_second = ticks_per_second
        self.seed = seed
        # The benchmark is attempt-driven: the agent gets `slice_attempts` shots at
        # the perfect slice. It is queried once per attempt and commits one slice;
        # the in-between `ticks_per_attempt` ticks just rotate the cone (so the next
        # attempt meets a fresh surface) and keep the replay smooth.
        self.slice_attempts = max(1, slice_attempts)
        self.ticks_per_attempt = max(1, ticks_per_attempt)

    def run_agent(self, agent: Agent, frame_callback: FrameCallback | None = None) -> AgentRunResult:
        rng = random.Random(f"{self.seed}:{agent.id}")
        frames: list[SimulationFrame] = []
        slices: list[SliceMetrics] = []
        action_history: list[ActionResult] = []
        cut_marks: list[dict[str, float]] = []
        knife_state = KnifeState()
        current_rotation_speed = self.environment.doner_rotation_speed
        current_heat_temperature = self.environment.heat_temperature
        rotation_angle = 0.0
        total_ticks = self.slice_attempts * self.ticks_per_attempt
        live_score = 0.0
        last_action = None
        decision_trace: dict[str, object] = {"mode": "pending"}
        action_label = "Waiting"

        for tick in range(total_ticks):
            time_seconds = tick / self.ticks_per_second
            if tick > 0:
                rotation_angle = (
                    rotation_angle + current_rotation_speed * math.tau / self.ticks_per_second
                ) % math.tau
            surface = self._sample_surface(
                rotation_angle,
                knife_state.location_from_top,
                current_heat_temperature,
            )

            attempt_index = tick // self.ticks_per_attempt
            is_attempt = tick % self.ticks_per_attempt == 0

            latest_slice = None
            if is_attempt:
                # One model query per attempt; the model sees every prior attempt
                # (the N-1 steps) plus all slices it has produced so far.
                observation = Observation(
                    time_remaining=float(self.slice_attempts - attempt_index),
                    doner_rotation_angle=rotation_angle,
                    doner_rotation_speed=current_rotation_speed,
                    heat_temperature=current_heat_temperature,
                    current_surface_geometry=surface["geometry"],
                    current_surface_freshness=surface["freshness"],
                    current_surface_cookedness=surface["cookedness"],
                    knife_state=knife_state,
                    previous_slice_metrics=list(slices),
                    action_history=list(action_history),
                )
                action = agent.act(observation)
                last_action = action
                decision_trace = agent.last_decision_trace
                current_rotation_speed = _approach(
                    current_rotation_speed, action.doner_rotation_speed, max_delta=0.08
                )
                current_heat_temperature = _approach(
                    current_heat_temperature, action.heat_temperature, max_delta=4.0
                )
                knife_state = KnifeState(
                    angle=action.knife_angle,
                    velocity=action.knife_velocity,
                    pressure=action.inward_pressure,
                    location_from_top=action.cut_location_from_top,
                    depth=action.cut_depth,
                )
                action_label = self._action_label(action.knife_velocity, action.inward_pressure)
                if self._is_cutting(action.knife_velocity, action.cut_depth):
                    latest_slice = self._make_slice(
                        tick=tick,
                        time_seconds=time_seconds,
                        action=action,
                        surface=surface,
                        previous_slices=slices,
                        rng=rng,
                    )
                    slices.append(latest_slice)
                    cut_marks = self._append_cut_mark(
                        cut_marks, rotation_angle, action.cut_location_from_top
                    )
                    live_score, _, _ = score_run(slices, self.slice_attempts)
                action_history.append(
                    ActionResult(
                        tick=tick,
                        time_seconds=round(time_seconds, 2),
                        attempt=attempt_index + 1,
                        action=action,
                        rotation_angle=round(rotation_angle, 4),
                        applied_rotation_speed=round(current_rotation_speed, 3),
                        applied_heat_temperature=round(current_heat_temperature, 2),
                        action_label=action_label,
                        produced_slice=latest_slice is not None,
                        decision=True,
                        agent_trace=decision_trace,
                        slice_metrics=latest_slice,
                    )
                )
            else:
                # Hold the committed action; only the cone keeps rotating.
                action = last_action
                decision_trace = {**agent.last_decision_trace, "mode": "held"}
                current_rotation_speed = _approach(
                    current_rotation_speed, action.doner_rotation_speed, max_delta=0.08
                )
                current_heat_temperature = _approach(
                    current_heat_temperature, action.heat_temperature, max_delta=4.0
                )

            frames.append(
                SimulationFrame(
                    tick=tick,
                    time_seconds=round(time_seconds, 2),
                    rotation_angle=round(rotation_angle, 4),
                    doner_rotation_speed=round(current_rotation_speed, 3),
                    heat_temperature=round(current_heat_temperature, 2),
                    knife_state=knife_state,
                    live_score=live_score,
                    action_label=action_label,
                    decision=is_attempt,
                    agent_trace=decision_trace,
                    latest_slice=latest_slice,
                    cut_marks=cut_marks.copy(),
                )
            )
            if frame_callback:
                frame_callback(frames.copy(), slices.copy(), live_score, tick, total_ticks)

        final_score, components, verdict = score_run(slices, self.slice_attempts)
        return AgentRunResult(
            agent_id=agent.id,
            agent_name=agent.name,
            final_score=final_score,
            component_scores=components,
            slices=slices,
            frames=frames,
            verdict=verdict,
        )

    def _sample_surface(
        self,
        angle: float,
        location_from_top: float,
        heat_temperature: float,
    ) -> dict[str, object]:
        height_factor = 1.0 - location_from_top
        radius = self.environment.cone_radius_top + (
            self.environment.cone_radius_bottom - self.environment.cone_radius_top
        ) * location_from_top
        irregularity_wave = (
            math.sin(angle * 3.0 + location_from_top * 7.0)
            + math.cos(angle * 5.0 - location_from_top * 4.0)
        ) * 0.5
        roughness = max(0.0, self.environment.surface_irregularity * (1.0 + irregularity_wave * 0.35))
        heat_factor = (heat_temperature - 120.0) / 140.0
        cookedness = _clamp(58.0 + heat_factor * 28.0 + math.cos(angle) * 9.0 - height_factor * 5.0)
        freshness = _clamp(86.0 - heat_factor * 9.0 - roughness * 16.0 + height_factor * 4.0)
        return {
            "geometry": {
                "radius_cm": round(radius, 3),
                "height_factor": round(height_factor, 3),
                "roughness": round(roughness, 3),
            },
            "freshness": freshness,
            "cookedness": cookedness,
        }

    def _make_slice(
        self,
        tick: int,
        time_seconds: float,
        action,
        surface: dict[str, object],
        previous_slices: list[SliceMetrics],
        rng: random.Random,
    ) -> SliceMetrics:
        geometry = surface["geometry"]
        assert isinstance(geometry, dict)
        radius_cm = float(geometry["radius_cm"])
        roughness = float(geometry["roughness"])

        # Normalize the physical controls (cm/s, N, mm) to 0-1 factors before the
        # physics so the model speaks real units while the scoring math is unchanged.
        angle_penalty = abs(action.knife_angle - 12.0) / 48.0
        velocity_factor = action.knife_velocity / KNIFE_VELOCITY_MAX_CM_S
        pressure_factor = action.inward_pressure / INWARD_PRESSURE_MAX_N
        depth_factor = action.cut_depth / CUT_DEPTH_MAX_MM
        vibration_bonus = min(action.vibration_frequency / 45.0, 1.0) * (
            action.vibration_amplitude / VIBRATION_AMPLITUDE_MAX_MM
        )

        thickness_mm = (
            1.8
            + depth_factor * 6.4
            + pressure_factor * 2.2
            - velocity_factor * 1.2
            + roughness * 1.4
            + rng.uniform(-0.35, 0.35)
        )
        thickness_mm = round(max(0.4, thickness_mm), 3)
        ideal_thickness_penalty = abs(thickness_mm - 4.2) * 13.0

        height_span = 6.0 + depth_factor * 9.0
        arc_span = 4.0 + velocity_factor * 8.0
        surface_area_cm2 = round(max(2.0, height_span * arc_span * (radius_cm / 12.0)), 3)
        volume_cm3 = round(surface_area_cm2 * (thickness_mm / 10.0), 3)

        tear_penalty = _clamp(
            pressure_factor * 28.0
            + velocity_factor * 22.0
            + angle_penalty * 32.0
            + roughness * 18.0
            - vibration_bonus * 16.0
        )
        waste_penalty = _clamp(
            max(0.0, depth_factor - 0.62) * 95.0
            + max(0.0, pressure_factor - 0.7) * 35.0
            + angle_penalty * 15.0
        )
        local_variance = self._thickness_variance(previous_slices, thickness_mm)
        uniformity_score = _clamp(100.0 - ideal_thickness_penalty - local_variance * 11.0)
        freshness_score = float(surface["freshness"])
        cookedness_score = _clamp(100.0 - abs(float(surface["cookedness"]) - 76.0) * 2.0)
        slice_score = _clamp(
            0.32 * uniformity_score
            + 0.22 * freshness_score
            + 0.18 * cookedness_score
            + 0.14 * (100.0 - tear_penalty)
            + 0.14 * (100.0 - waste_penalty)
        )
        valid = 2.0 <= thickness_mm <= 8.5 and surface_area_cm2 >= 8.0 and tear_penalty < 70.0
        operation_log = self._operation_log(
            action=action,
            thickness_mm=thickness_mm,
            surface_area_cm2=surface_area_cm2,
            tear_penalty=tear_penalty,
            waste_penalty=waste_penalty,
            uniformity_score=uniformity_score,
        )

        return SliceMetrics(
            tick=tick,
            time_seconds=round(time_seconds, 2),
            thickness_mm=thickness_mm,
            thickness_variance=round(local_variance, 3),
            surface_area_cm2=surface_area_cm2,
            volume_cm3=volume_cm3,
            freshness_score=round(freshness_score, 2),
            cookedness_score=round(cookedness_score, 2),
            tear_penalty=round(tear_penalty, 2),
            waste_penalty=round(waste_penalty, 2),
            uniformity_score=round(uniformity_score, 2),
            slice_score=round(slice_score, 2),
            operation_log=operation_log,
            valid=valid,
        )

    def _operation_log(
        self,
        action,
        thickness_mm: float,
        surface_area_cm2: float,
        tear_penalty: float,
        waste_penalty: float,
        uniformity_score: float,
    ) -> list[str]:
        log = [
            f"angle {action.knife_angle:.1f}deg",
            f"velocity {action.knife_velocity:.1f}cm/s",
            f"pressure {action.inward_pressure:.1f}N",
            f"depth {action.cut_depth:.1f}mm",
            f"height {action.cut_location_from_top:.2f}",
            f"rotation {action.doner_rotation_speed:.2f}rps",
            f"heat {action.heat_temperature:.0f}C",
        ]
        if action.vibration_frequency > 0 and action.vibration_amplitude > 0:
            log.append(
                f"vibration {action.vibration_frequency:.0f}Hz/{action.vibration_amplitude:.2f}mm"
            )
        if thickness_mm > 6.5:
            log.append("thick slice correction needed")
        elif thickness_mm < 3.0:
            log.append("very thin shave")
        else:
            log.append("target thickness band")
        if surface_area_cm2 > 80:
            log.append("wide sheet removed")
        if tear_penalty > 32:
            log.append("tear risk elevated")
        if waste_penalty > 18:
            log.append("waste risk elevated")
        if uniformity_score > 88:
            log.append("uniform pass")
        elif uniformity_score < 65:
            log.append("inconsistent pass")
        return log

    def _thickness_variance(self, previous_slices: list[SliceMetrics], thickness_mm: float) -> float:
        recent = [slice_.thickness_mm for slice_ in previous_slices[-8:]] + [thickness_mm]
        return 0.0 if len(recent) <= 1 else pvariance(recent)

    def _append_cut_mark(
        self, cut_marks: list[dict[str, float]], rotation_angle: float, location: float
    ) -> list[dict[str, float]]:
        next_marks = cut_marks[-24:] + [
            {
                "angle": round(rotation_angle, 4),
                "location_from_top": round(location, 3),
                "intensity": 1.0,
            }
        ]
        return next_marks

    def _is_cutting(self, knife_velocity: float, cut_depth: float) -> bool:
        # Needs enough draw speed (cm/s) and blade penetration (mm) to shave.
        return (
            knife_velocity > 0.18 * KNIFE_VELOCITY_MAX_CM_S
            and cut_depth > 0.16 * CUT_DEPTH_MAX_MM
        )

    def _action_label(self, velocity: float, pressure: float) -> str:
        if velocity > 0.72 * KNIFE_VELOCITY_MAX_CM_S or pressure > 0.72 * INWARD_PRESSURE_MAX_N:
            return "Power slice"
        if velocity < 0.4 * KNIFE_VELOCITY_MAX_CM_S and pressure < 0.45 * INWARD_PRESSURE_MAX_N:
            return "Careful shave"
        return "Balanced cut"


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _approach(current: float, target: float, max_delta: float) -> float:
    if target > current:
        return min(target, current + max_delta)
    return max(target, current - max_delta)

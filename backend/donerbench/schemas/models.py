from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

# Physical upper bounds for the controls, so the model reasons in real units
# (cm/s, newtons, millimetres) instead of abstract 0-1 dials. The simulation
# normalizes each control by its max before applying physics, so changing a
# bound here only changes the units the model speaks, not the scoring.
KNIFE_VELOCITY_MAX_CM_S = 50.0
INWARD_PRESSURE_MAX_N = 40.0
VIBRATION_AMPLITUDE_MAX_MM = 4.0
CUT_DEPTH_MAX_MM = 20.0


class AgentAction(BaseModel):
    doner_rotation_speed: float = Field(ge=0.2, le=3.0)  # rotations per second
    heat_temperature: float = Field(ge=120.0, le=260.0)  # degrees Celsius
    knife_angle: float = Field(ge=-60.0, le=60.0)  # degrees
    knife_velocity: float = Field(ge=0.0, le=KNIFE_VELOCITY_MAX_CM_S)  # cm/s
    inward_pressure: float = Field(ge=0.0, le=INWARD_PRESSURE_MAX_N)  # newtons
    vibration_frequency: float = Field(ge=0.0, le=80.0)  # Hz
    vibration_amplitude: float = Field(ge=0.0, le=VIBRATION_AMPLITUDE_MAX_MM)  # mm
    cut_location_from_top: float = Field(ge=0.0, le=1.0)  # fraction of cone height
    cut_depth: float = Field(ge=0.0, le=CUT_DEPTH_MAX_MM)  # mm of blade penetration


class KnifeState(BaseModel):
    angle: float = 0.0
    velocity: float = 0.0
    pressure: float = 0.0
    location_from_top: float = 0.5
    depth: float = 0.0


class ActionResult(BaseModel):
    tick: int
    time_seconds: float
    attempt: int = 0
    action: AgentAction
    rotation_angle: float
    applied_rotation_speed: float
    applied_heat_temperature: float
    action_label: str
    produced_slice: bool
    decision: bool = True
    agent_trace: dict[str, object] = Field(default_factory=dict)
    slice_metrics: Optional["SliceMetrics"] = None


class EnvironmentConfig(BaseModel):
    doner_rotation_speed: float = Field(default=0.75, gt=0.0, le=3.0)
    heat_temperature: float = Field(default=185.0, ge=120.0, le=260.0)
    cone_height: float = Field(default=45.0, ge=20.0, le=90.0)
    cone_radius_top: float = Field(default=9.0, ge=3.0, le=20.0)
    cone_radius_bottom: float = Field(default=16.0, ge=5.0, le=30.0)
    surface_irregularity: float = Field(default=0.18, ge=0.0, le=1.0)


class Observation(BaseModel):
    time_remaining: float
    doner_rotation_angle: float
    doner_rotation_speed: float
    heat_temperature: float
    current_surface_geometry: dict[str, float]
    current_surface_freshness: float
    current_surface_cookedness: float
    knife_state: KnifeState
    previous_slice_metrics: list["SliceMetrics"]
    action_history: list[ActionResult] = Field(default_factory=list)


class SliceMetrics(BaseModel):
    tick: int
    time_seconds: float
    thickness_mm: float
    thickness_variance: float
    surface_area_cm2: float
    volume_cm3: float
    freshness_score: float
    cookedness_score: float
    tear_penalty: float
    waste_penalty: float
    uniformity_score: float
    slice_score: float
    operation_log: list[str] = Field(default_factory=list)
    valid: bool


class SimulationFrame(BaseModel):
    tick: int
    time_seconds: float
    rotation_angle: float
    doner_rotation_speed: float
    heat_temperature: float
    knife_state: KnifeState
    live_score: float
    action_label: str
    decision: bool = True
    agent_trace: dict[str, object] = Field(default_factory=dict)
    latest_slice: SliceMetrics | None = None
    cut_marks: list[dict[str, float]] = Field(default_factory=list)


class AgentInfo(BaseModel):
    id: str
    name: str
    description: str
    provider: str = "builtin"
    model: str | None = None
    base_url: str | None = None
    base_url_env: str | None = None
    requires_api_key: bool = False
    api_key_env: str | None = None
    api_key_configured: bool = True
    endpoint_configured: bool = True


class AgentRunResult(BaseModel):
    agent_id: str
    agent_name: str
    final_score: float
    component_scores: dict[str, float]
    slices: list[SliceMetrics]
    frames: list[SimulationFrame]
    verdict: str


class LeaderboardEntry(BaseModel):
    rank: int
    agent_id: str
    agent_name: str
    final_score: float
    valid_slice_count: int
    average_thickness: float
    thickness_variance: float
    average_area: float
    average_freshness: float
    waste_percentage: float
    tear_penalty: float
    verdict: str


class BenchmarkRequest(BaseModel):
    agent_ids: list[str] = Field(default_factory=lambda: ["gpt-5.5", "claude-sonnet-4.6"])
    seed: int = 42
    slice_attempts: int = Field(default=30, ge=1, le=200)
    ticks_per_second: int = Field(default=10, ge=2, le=30)
    environment: EnvironmentConfig = Field(default_factory=EnvironmentConfig)


class BenchmarkResult(BaseModel):
    seed: int
    slice_attempts: int
    ticks_per_second: int
    environment: EnvironmentConfig
    status: Literal["running", "complete"] = "complete"
    runs: list[AgentRunResult]
    leaderboard: list[LeaderboardEntry]


class BenchmarkJobStart(BaseModel):
    job_id: str
    status: Literal["queued", "running", "complete", "failed"]


class BenchmarkJobStatus(BaseModel):
    job_id: str
    status: Literal["queued", "running", "complete", "failed"]
    progress: float = Field(ge=0.0, le=1.0)
    message: str = ""
    partial_result: BenchmarkResult | None = None
    result: BenchmarkResult | None = None
    error: str | None = None

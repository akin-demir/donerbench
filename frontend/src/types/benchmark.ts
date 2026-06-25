export interface AgentAction {
  doner_rotation_speed: number;
  heat_temperature: number;
  knife_angle: number;
  knife_velocity: number;
  inward_pressure: number;
  vibration_frequency: number;
  vibration_amplitude: number;
  cut_location_from_top: number;
  cut_depth: number;
}

export interface KnifeState {
  angle: number;
  velocity: number;
  pressure: number;
  location_from_top: number;
  depth: number;
}

export interface EnvironmentConfig {
  doner_rotation_speed: number;
  heat_temperature: number;
  cone_height: number;
  cone_radius_top: number;
  cone_radius_bottom: number;
  surface_irregularity: number;
}

export interface AgentInfo {
  id: string;
  name: string;
  description: string;
  provider: string;
  model: string | null;
  base_url: string | null;
  base_url_env: string | null;
  requires_api_key: boolean;
  api_key_env: string | null;
  api_key_configured: boolean;
  endpoint_configured: boolean;
}

export interface SliceMetrics {
  tick: number;
  time_seconds: number;
  thickness_mm: number;
  thickness_variance: number;
  surface_area_cm2: number;
  volume_cm3: number;
  freshness_score: number;
  cookedness_score: number;
  tear_penalty: number;
  waste_penalty: number;
  uniformity_score: number;
  slice_score: number;
  operation_log: string[];
  valid: boolean;
}

export interface SimulationFrame {
  tick: number;
  time_seconds: number;
  rotation_angle: number;
  doner_rotation_speed: number;
  heat_temperature: number;
  knife_state: KnifeState;
  live_score: number;
  action_label: string;
  decision: boolean;
  agent_trace: Record<string, unknown>;
  latest_slice: SliceMetrics | null;
  cut_marks: Array<{
    angle: number;
    location_from_top: number;
    intensity: number;
  }>;
}

export interface AgentRunResult {
  agent_id: string;
  agent_name: string;
  final_score: number;
  component_scores: Record<string, number>;
  slices: SliceMetrics[];
  frames: SimulationFrame[];
  verdict: string;
}

export interface LeaderboardEntry {
  rank: number;
  agent_id: string;
  agent_name: string;
  final_score: number;
  valid_slice_count: number;
  average_thickness: number;
  thickness_variance: number;
  average_area: number;
  average_freshness: number;
  waste_percentage: number;
  tear_penalty: number;
  verdict: string;
}

export interface BenchmarkRequest {
  agent_ids: string[];
  seed: number;
  duration_seconds: number;
  ticks_per_second: number;
  decision_interval_seconds: number;
  environment: EnvironmentConfig;
}

export interface BenchmarkResult {
  seed: number;
  duration_seconds: number;
  ticks_per_second: number;
  environment: EnvironmentConfig;
  status: 'running' | 'complete';
  runs: AgentRunResult[];
  leaderboard: LeaderboardEntry[];
}

export interface BenchmarkJobStart {
  job_id: string;
  status: 'queued' | 'running' | 'complete' | 'failed';
}

export interface BenchmarkJobStatus {
  job_id: string;
  status: 'queued' | 'running' | 'complete' | 'failed';
  progress: number;
  message: string;
  partial_result: BenchmarkResult | null;
  result: BenchmarkResult | null;
  error: string | null;
}

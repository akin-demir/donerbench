import { create } from 'zustand';
import { fetchAgents, fetchBenchmarkJob, startBenchmarkJob } from '../api/client';
import type { AgentInfo, BenchmarkRequest, BenchmarkResult, EnvironmentConfig } from '../types/benchmark';

const defaultEnvironment: EnvironmentConfig = {
  doner_rotation_speed: 0.75,
  heat_temperature: 185,
  cone_height: 45,
  cone_radius_top: 9,
  cone_radius_bottom: 16,
  surface_irregularity: 0.18
};

interface BenchmarkState {
  agents: AgentInfo[];
  selectedAgentIds: string[];
  seed: number;
  durationSeconds: number;
  ticksPerSecond: number;
  decisionIntervalSeconds: number;
  environment: EnvironmentConfig;
  result: BenchmarkResult | null;
  frameIndex: number;
  isPlaying: boolean;
  isLoading: boolean;
  error: string | null;
  jobId: string | null;
  jobProgress: number;
  jobMessage: string;
  loadAgents: () => Promise<void>;
  toggleAgent: (agentId: string) => void;
  setSeed: (seed: number) => void;
  setDuration: (durationSeconds: number) => void;
  setDecisionInterval: (decisionIntervalSeconds: number) => void;
  setEnvironmentValue: (key: keyof EnvironmentConfig, value: number) => void;
  run: () => Promise<void>;
  setFrameIndex: (frameIndex: number) => void;
  setPlaying: (isPlaying: boolean) => void;
  advanceFrame: () => void;
}

export const useBenchmarkStore = create<BenchmarkState>((set, get) => ({
  agents: [],
  selectedAgentIds: ['gpt-5.5', 'claude-sonnet-4.6'],
  seed: 42,
  durationSeconds: 60,
  ticksPerSecond: 10,
  decisionIntervalSeconds: 1.0,
  environment: defaultEnvironment,
  result: null,
  frameIndex: 0,
  isPlaying: false,
  isLoading: false,
  error: null,
  jobId: null,
  jobProgress: 0,
  jobMessage: '',

  loadAgents: async () => {
    set({ isLoading: true, error: null });
    try {
      const agents = await fetchAgents();
      const selectableAgents = agents.filter(isAgentSelectable);
      const selectedAgentIds = get().selectedAgentIds.filter((id) =>
        selectableAgents.some((agent) => agent.id === id)
      );
      set({
        agents,
        selectedAgentIds: selectedAgentIds.length
          ? selectedAgentIds
          : selectableAgents.slice(0, 2).map((agent) => agent.id),
        isLoading: false
      });
    } catch (error) {
      set({ error: error instanceof Error ? error.message : 'Unable to load agents', isLoading: false });
    }
  },

  toggleAgent: (agentId) => {
    const agent = get().agents.find((candidate) => candidate.id === agentId);
    if (agent && !isAgentSelectable(agent)) return;
    const selected = get().selectedAgentIds;
    const next = selected.includes(agentId)
      ? selected.filter((id) => id !== agentId)
      : [...selected, agentId];
    set({ selectedAgentIds: next.slice(0, 4) });
  },

  setSeed: (seed) => set({ seed }),
  setDuration: (durationSeconds) => set({ durationSeconds }),
  setDecisionInterval: (decisionIntervalSeconds) => set({ decisionIntervalSeconds }),
  setEnvironmentValue: (key, value) =>
    set((state) => ({ environment: { ...state.environment, [key]: value } })),

  run: async () => {
    const state = get();
    const request: BenchmarkRequest = {
      agent_ids: state.selectedAgentIds,
      seed: state.seed,
      duration_seconds: state.durationSeconds,
      ticks_per_second: state.ticksPerSecond,
      decision_interval_seconds: state.decisionIntervalSeconds,
      environment: state.environment
    };
    set({
      isLoading: true,
      error: null,
      isPlaying: false,
      frameIndex: 0,
      result: null,
      jobId: null,
      jobProgress: 0,
      jobMessage: 'Starting benchmark'
    });
    try {
      const job = await startBenchmarkJob(request);
      set({ jobId: job.job_id, jobProgress: 0.02, jobMessage: 'Queued' });
      const result = await pollBenchmarkJob(
        job.job_id,
        (progress, message) => {
          set({ jobProgress: progress, jobMessage: message });
        },
        (partialResult) => {
          set((current) => ({
            result: partialResult,
            isPlaying: true,
            frameIndex: clampFrameIndex(current.frameIndex, partialResult)
          }));
        }
      );
      set({
        result,
        isLoading: false,
        isPlaying: true,
        frameIndex: 0,
        jobProgress: 1,
        jobMessage: 'Benchmark complete'
      });
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Benchmark failed',
        isLoading: false,
        jobMessage: 'Benchmark failed'
      });
    }
  },

  setFrameIndex: (frameIndex) => set({ frameIndex }),
  setPlaying: (isPlaying) => set({ isPlaying }),
  advanceFrame: () => {
    const { isLoading, result } = get();
    if (!result) return;
    const maxFrame = Math.max(...result.runs.map((run) => run.frames.length - 1));
    const next = get().frameIndex + 1;
    set({
      frameIndex: next > maxFrame ? maxFrame : next,
      isPlaying: isLoading || next < maxFrame
    });
  }
}));

async function pollBenchmarkJob(
  jobId: string,
  onProgress: (progress: number, message: string) => void,
  onPartial: (result: BenchmarkResult) => void
): Promise<BenchmarkResult> {
  for (;;) {
    const status = await fetchBenchmarkJob(jobId);
    onProgress(status.progress, status.message);
    if (status.partial_result) {
      onPartial(status.partial_result);
    }
    if (status.status === 'complete' && status.result) {
      return status.result;
    }
    if (status.status === 'failed') {
      throw new Error(status.error || 'Benchmark job failed');
    }
    await sleep(1000);
  }
}

function isAgentSelectable(agent: AgentInfo) {
  const keyReady = !agent.requires_api_key || agent.api_key_configured;
  return keyReady && agent.endpoint_configured;
}

function sleep(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function clampFrameIndex(frameIndex: number, result: BenchmarkResult) {
  const maxFrame = Math.max(0, ...result.runs.map((run) => run.frames.length - 1));
  return Math.min(frameIndex, maxFrame);
}

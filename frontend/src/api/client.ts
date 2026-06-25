import type {
  AgentInfo,
  BenchmarkJobStart,
  BenchmarkJobStatus,
  BenchmarkRequest,
  BenchmarkResult
} from '../types/benchmark';

export async function fetchAgents(): Promise<AgentInfo[]> {
  const response = await fetch('/api/agents');
  if (!response.ok) {
    throw new Error('Failed to load agents');
  }
  return response.json();
}

export async function runBenchmark(request: BenchmarkRequest): Promise<BenchmarkResult> {
  const response = await fetch('/api/benchmark/run', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request)
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || 'Benchmark run failed');
  }
  return response.json();
}

export async function startBenchmarkJob(request: BenchmarkRequest): Promise<BenchmarkJobStart> {
  const response = await fetch('/api/benchmark/jobs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request)
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || 'Failed to start benchmark job');
  }
  return response.json();
}

export async function fetchBenchmarkJob(jobId: string): Promise<BenchmarkJobStatus> {
  const response = await fetch(`/api/benchmark/jobs/${jobId}`);
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || 'Failed to fetch benchmark job');
  }
  return response.json();
}

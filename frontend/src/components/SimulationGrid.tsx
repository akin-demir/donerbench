import { AgentViewport } from './AgentViewport';
import { useBenchmarkStore } from '../state/benchmarkStore';

export function SimulationGrid() {
  const { result, frameIndex } = useBenchmarkStore();

  if (!result) {
    return (
      <section className="empty-viewer">
        <div>
          <h2>Benchmark viewer</h2>
          <p>Select agents and run the benchmark to generate deterministic replay frames.</p>
        </div>
      </section>
    );
  }

  return (
    <section className={`simulation-grid agents-${result.runs.length}`}>
      {result.runs.map((run) => (
        <AgentViewport
          key={run.agent_id}
          run={run}
          frame={run.frames[Math.min(frameIndex, run.frames.length - 1)]}
          environment={result.environment}
        />
      ))}
    </section>
  );
}

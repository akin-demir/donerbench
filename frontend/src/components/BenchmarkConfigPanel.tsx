import { Gauge, SlidersHorizontal } from 'lucide-react';
import { useBenchmarkStore } from '../state/benchmarkStore';

export function BenchmarkConfigPanel() {
  const {
    seed,
    durationSeconds,
    decisionIntervalSeconds,
    environment,
    setSeed,
    setDuration,
    setDecisionInterval,
    setEnvironmentValue
  } = useBenchmarkStore();

  return (
    <section className="panel">
      <div className="panel-heading">
        <SlidersHorizontal size={18} />
        <h2>Configuration</h2>
      </div>
      <label className="field">
        <span>Seed</span>
        <input type="number" value={seed} onChange={(event) => setSeed(Number(event.target.value))} />
      </label>
      <label className="field">
        <span>Duration</span>
        <input
          type="number"
          min={5}
          max={120}
          value={durationSeconds}
          onChange={(event) => setDuration(Number(event.target.value))}
        />
      </label>
      <label className="field">
        <span>Decision interval (s)</span>
        <input
          type="number"
          min={0.1}
          max={10}
          step={0.1}
          value={decisionIntervalSeconds}
          onChange={(event) => setDecisionInterval(Number(event.target.value))}
        />
        <small>
          Model is queried every {decisionIntervalSeconds}s (~
          {Math.max(1, Math.round(durationSeconds / decisionIntervalSeconds))} calls/agent); the
          action is held between queries.
        </small>
      </label>
      <label className="range-field">
        <span>
          <Gauge size={15} />
          Surface
          <strong>{environment.surface_irregularity.toFixed(2)}</strong>
        </span>
        <input
          type="range"
          min={0}
          max={0.8}
          step={0.01}
          value={environment.surface_irregularity}
          onChange={(event) => setEnvironmentValue('surface_irregularity', Number(event.target.value))}
        />
      </label>
    </section>
  );
}

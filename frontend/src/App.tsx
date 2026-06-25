import { useEffect } from 'react';
import { Pause, Play, TimerReset } from 'lucide-react';
import { AgentSelectionPanel } from './components/AgentSelectionPanel';
import { BenchmarkConfigPanel } from './components/BenchmarkConfigPanel';
import { LeaderboardTable } from './components/LeaderboardTable';
import { SimulationGrid } from './components/SimulationGrid';
import { SliceComparisonTable } from './components/SliceComparisonTable';
import { useBenchmarkStore } from './state/benchmarkStore';

export function App() {
  const {
    loadAgents,
    result,
    frameIndex,
    isPlaying,
    setPlaying,
    setFrameIndex,
    advanceFrame,
    isLoading,
    error,
    jobProgress,
    jobMessage
  } = useBenchmarkStore();

  useEffect(() => {
    void loadAgents();
  }, [loadAgents]);

  useEffect(() => {
    if (!isPlaying) return;
    const timer = window.setInterval(() => advanceFrame(), 100);
    return () => window.clearInterval(timer);
  }, [advanceFrame, isPlaying]);

  const maxFrame = result ? Math.max(...result.runs.map((run) => run.frames.length - 1)) : 0;
  const elapsed = result ? (frameIndex / result.ticks_per_second).toFixed(1) : '0.0';

  return (
    <main className="app-shell">
      <section className="control-rail">
        <div className="brand-block">
          <img
            className="brand-logo"
            src="/logo.png"
            alt="DönerBench — The Perfect Slice Benchmark"
          />
        </div>
        <AgentSelectionPanel />
        <BenchmarkConfigPanel />
      </section>

      <section className="workspace">
        <div className="run-toolbar">
          <div>
            <span className="eyebrow">Simulated service window</span>
            <strong>{elapsed}s</strong>
          </div>
          <div className="playback-controls">
            <button
              className="icon-button"
              type="button"
              aria-label={isPlaying ? 'Pause' : 'Play'}
              title={isPlaying ? 'Pause' : 'Play'}
              disabled={!result}
              onClick={() => setPlaying(!isPlaying)}
            >
              {isPlaying ? <Pause size={18} /> : <Play size={18} />}
            </button>
            <button
              className="icon-button"
              type="button"
              aria-label="Restart"
              title="Restart"
              disabled={!result}
              onClick={() => setFrameIndex(0)}
            >
              <TimerReset size={18} />
            </button>
            <input
              aria-label="Timeline"
              type="range"
              min={0}
              max={maxFrame}
              value={frameIndex}
              disabled={!result}
              onChange={(event) => setFrameIndex(Number(event.target.value))}
            />
          </div>
        </div>

        {error && <div className="status-banner error">{error}</div>}
        {isLoading && (
          <div className="status-banner">
            {jobMessage || 'Running benchmark...'} {Math.round(jobProgress * 100)}%
          </div>
        )}

        <SimulationGrid />
        <LeaderboardTable />
        <SliceComparisonTable />
      </section>
    </main>
  );
}

import { Flame, Gauge, RotateCw, Scissors, Timer } from 'lucide-react';
import { DonerScene } from '../rendering/DonerScene';
import type { AgentRunResult, EnvironmentConfig, SimulationFrame } from '../types/benchmark';

interface AgentViewportProps {
  run: AgentRunResult;
  frame: SimulationFrame;
  environment: EnvironmentConfig;
}

export function AgentViewport({ run, frame, environment }: AgentViewportProps) {
  const latest = frame.latest_slice;
  const traceMode = typeof frame.agent_trace.mode === 'string' ? frame.agent_trace.mode : 'pending';

  return (
    <article className="viewport">
      <DonerScene frame={frame} environment={environment} />
      <div className="metrics-overlay">
        <div className="viewport-title">
          <strong>{run.agent_name}</strong>
          <span>{frame.action_label} / {traceMode}</span>
        </div>
        <div className="metric-row">
          <span>
            <Timer size={14} />
            {frame.time_seconds.toFixed(1)}s
          </span>
          <span>
            <Gauge size={14} />
            {frame.live_score.toFixed(1)}
          </span>
          <span>
            <Scissors size={14} />
            {run.slices.filter((slice) => slice.tick <= frame.tick).length}
          </span>
          <span>
            <RotateCw size={14} />
            {frame.doner_rotation_speed.toFixed(2)}
          </span>
          <span>
            <Flame size={14} />
            {frame.heat_temperature.toFixed(0)}C
          </span>
        </div>
        {latest && (
          <div className="slice-flash">
            <span>{latest.thickness_mm.toFixed(1)}mm</span>
            <span>{latest.slice_score.toFixed(0)}</span>
          </div>
        )}
      </div>
    </article>
  );
}

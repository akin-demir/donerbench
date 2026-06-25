import { Rows3 } from 'lucide-react';
import { useMemo } from 'react';
import { useBenchmarkStore } from '../state/benchmarkStore';

export function SliceComparisonTable() {
  const { frameIndex, result } = useBenchmarkStore();
  const rows = useMemo(() => {
    if (!result) return [];
    return result.runs.flatMap((run) => {
      const frame = run.frames[Math.min(frameIndex, run.frames.length - 1)];
      const visibleTick = frame?.tick ?? Number.POSITIVE_INFINITY;
      return run.slices
        .filter((slice) => slice.tick <= visibleTick)
        .slice(-8)
        .map((slice) => ({
          agent: run.agent_name,
          ...slice
        }));
    });
  }, [frameIndex, result]);

  if (!result) return null;

  return (
    <section className="data-section">
      <div className="section-heading">
        <Rows3 size={18} />
        <h2>Recent Slices</h2>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Agent</th>
              <th>Time</th>
              <th>Score</th>
              <th>Thickness</th>
              <th>Area</th>
              <th>Fresh</th>
              <th>Cooked</th>
              <th>Waste</th>
              <th>Tear</th>
              <th>Operations</th>
              <th>Valid</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((slice) => (
              <tr key={`${slice.agent}-${slice.tick}`}>
                <td>{slice.agent}</td>
                <td>{slice.time_seconds.toFixed(1)}s</td>
                <td>{slice.slice_score.toFixed(1)}</td>
                <td>{slice.thickness_mm.toFixed(2)}mm</td>
                <td>{slice.surface_area_cm2.toFixed(1)}cm2</td>
                <td>{slice.freshness_score.toFixed(1)}</td>
                <td>{slice.cookedness_score.toFixed(1)}</td>
                <td>{slice.waste_penalty.toFixed(1)}</td>
                <td>{slice.tear_penalty.toFixed(1)}</td>
                <td className="operation-cell">{slice.operation_log.join(' -> ')}</td>
                <td>{slice.valid ? 'Yes' : 'No'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

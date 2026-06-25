import { Trophy } from 'lucide-react';
import { useBenchmarkStore } from '../state/benchmarkStore';

export function LeaderboardTable() {
  const { result } = useBenchmarkStore();
  if (!result) return null;

  return (
    <section className="data-section">
      <div className="section-heading">
        <Trophy size={18} />
        <h2>Leaderboard</h2>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Rank</th>
              <th>Agent</th>
              <th>Score</th>
              <th>Valid</th>
              <th>Thickness</th>
              <th>Variance</th>
              <th>Area</th>
              <th>Freshness</th>
              <th>Waste</th>
              <th>Tear</th>
              <th>Verdict</th>
            </tr>
          </thead>
          <tbody>
            {result.leaderboard.map((entry) => (
              <tr key={entry.agent_id}>
                <td>{entry.rank}</td>
                <td>{entry.agent_name}</td>
                <td>{entry.final_score.toFixed(2)}</td>
                <td>{entry.valid_slice_count}</td>
                <td>{entry.average_thickness.toFixed(2)}mm</td>
                <td>{entry.thickness_variance.toFixed(3)}</td>
                <td>{entry.average_area.toFixed(1)}cm2</td>
                <td>{entry.average_freshness.toFixed(1)}</td>
                <td>{entry.waste_percentage.toFixed(1)}%</td>
                <td>{entry.tear_penalty.toFixed(1)}</td>
                <td>{entry.verdict}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

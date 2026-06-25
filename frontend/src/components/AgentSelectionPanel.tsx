import { Bot, Swords } from 'lucide-react';
import { useBenchmarkStore } from '../state/benchmarkStore';

export function AgentSelectionPanel() {
  const { agents, selectedAgentIds, toggleAgent, run, isLoading } = useBenchmarkStore();

  return (
    <section className="panel">
      <div className="panel-heading">
        <Bot size={18} />
        <h2>Agents</h2>
      </div>
      <div className="agent-list">
        {agents.map((agent) => {
          const selected = selectedAgentIds.includes(agent.id);
          const missingKey = agent.requires_api_key && !agent.api_key_configured;
          const missingEndpoint = !agent.endpoint_configured;
          const unavailable = missingKey || missingEndpoint;
          return (
            <label
              className={`agent-row ${selected ? 'selected' : ''} ${unavailable ? 'unavailable' : ''}`}
              key={agent.id}
            >
              <input
                type="checkbox"
                checked={selected}
                disabled={unavailable || (!selected && selectedAgentIds.length >= 4)}
                onChange={() => toggleAgent(agent.id)}
              />
              <span>
                <strong>{agent.name}</strong>
                <small>{agent.description}</small>
                <small className="agent-meta">
                  {agent.provider}
                  {agent.model ? ` / ${agent.model}` : ''}
                </small>
                {agent.requires_api_key && (
                  <small className={agent.api_key_configured ? 'key-ok' : 'key-missing'}>
                    {agent.api_key_env} {agent.api_key_configured ? 'configured' : 'missing'}
                  </small>
                )}
                {missingEndpoint && (
                  <small className="key-missing">
                    {agent.base_url_env ?? 'endpoint'} missing
                  </small>
                )}
              </span>
            </label>
          );
        })}
      </div>
      <button
        className="primary-button"
        type="button"
        disabled={isLoading || selectedAgentIds.length === 0}
        onClick={() => void run()}
      >
        <Swords size={18} />
        Run Benchmark
      </button>
    </section>
  );
}

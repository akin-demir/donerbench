from donerbench.agents import build_agent, list_agents


def test_registry_lists_model_agents() -> None:
    agents = list_agents()
    agent_ids = {agent.id for agent in agents}

    assert "gpt-5.5" in agent_ids
    assert "claude-sonnet-4.6" in agent_ids
    assert "claude-opus-4.6" in agent_ids
    assert "qwen3.6" in agent_ids
    assert "random" not in agent_ids
    assert "conservative" not in agent_ids
    assert "aggressive" not in agent_ids
    assert "balanced" not in agent_ids


def test_api_key_backed_agent_reports_missing_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    agent = next(agent for agent in list_agents() if agent.id == "gpt-5.5")

    try:
        build_agent("gpt-5.5", seed=1)
    except ValueError as exc:
        assert "OPENAI_API_KEY" in str(exc)
    else:
        raise AssertionError("API-key-backed agent unexpectedly built")

    assert agent.requires_api_key
    assert not agent.api_key_configured


def test_api_key_backed_agent_can_be_built_when_key_exists(monkeypatch) -> None:
    monkeypatch.setenv("DONERBENCH_AGENT_MODE", "profile")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    agent = build_agent("gpt-5.5", seed=1)

    assert agent.id == "gpt-5.5"

import httpx
import logging

from donerbench.agents import build_agent
from donerbench.schemas import KnifeState, Observation


def _observation() -> Observation:
    return Observation(
        time_remaining=60.0,
        doner_rotation_angle=0.0,
        doner_rotation_speed=0.75,
        heat_temperature=185.0,
        current_surface_geometry={"radius_cm": 12.0, "height_factor": 0.5, "roughness": 0.2},
        current_surface_freshness=82.0,
        current_surface_cookedness=76.0,
        knife_state=KnifeState(),
        previous_slice_metrics=[],
        action_history=[],
    )


def test_openai_agent_sends_observation_to_responses_api_and_parses_action(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai")
    captured: dict[str, object] = {}

    def fake_post(url, headers, json, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return httpx.Response(
            200,
            json={
                "output": [
                    {
                        "content": [
                            {
                                "type": "output_text",
                                "text": (
                                '{"doner_rotation_speed":0.9,"heat_temperature":190,'
                                '"knife_angle":10,"knife_velocity":0.5,"inward_pressure":0.4,'
                                '"vibration_frequency":30,"vibration_amplitude":0.3,'
                                '"cut_location_from_top":0.45,"cut_depth":0.5}'
                            )
                            }
                        ]
                    }
                ]
            },
            request=httpx.Request("POST", "https://api.openai.com/v1/responses"),
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    agent = build_agent("gpt-5.5", seed=1)

    action = agent.act(_observation())

    assert action.knife_angle == 10
    assert captured["url"] == "https://api.openai.com/v1/responses"
    assert "Authorization" in captured["headers"]
    assert "temperature" not in captured["json"]
    assert "attempts_remaining" in captured["json"]["input"]
    assert agent.last_decision_trace["mode"] == "live"
    assert agent.last_decision_trace["request_payload"]["attempts_remaining"] == 60


def test_live_agent_logs_request_and_response_summary(monkeypatch, caplog) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai")

    def fake_post(url, headers, json, timeout):
        return httpx.Response(
            200,
            json={
                "output_text": (
                    '{"doner_rotation_speed":0.9,"heat_temperature":190,'
                    '"knife_angle":10,"knife_velocity":0.5,"inward_pressure":0.4,'
                    '"vibration_frequency":30,"vibration_amplitude":0.3,'
                    '"cut_location_from_top":0.45,"cut_depth":0.5}'
                )
            },
            request=httpx.Request("POST", "https://api.openai.com/v1/responses"),
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    agent = build_agent("gpt-5.5", seed=1)

    with caplog.at_level(logging.INFO, logger="donerbench.agents"):
        agent.act(_observation())

    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert "LLM request agent=gpt-5.5" in log_text
    assert "LLM response agent=gpt-5.5" in log_text
    assert "history_items=0" in log_text


def test_profile_mode_is_explicit(monkeypatch) -> None:
    monkeypatch.setenv("DONERBENCH_AGENT_MODE", "profile")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai")
    agent = build_agent("gpt-5.5", seed=1)

    action = agent.act(_observation())

    assert 0.2 <= action.doner_rotation_speed <= 3.0
    assert agent.last_decision_trace["mode"] == "profile"


def test_live_agent_uses_unified_markdown_prompt(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai")
    captured: dict[str, object] = {}

    def fake_post(url, headers, json, timeout):
        captured["json"] = json
        return httpx.Response(
            200,
            json={
                "output_text": (
                    '{"doner_rotation_speed":0.9,"heat_temperature":190,'
                    '"knife_angle":10,"knife_velocity":0.5,"inward_pressure":0.4,'
                    '"vibration_frequency":30,"vibration_amplitude":0.3,'
                    '"cut_location_from_top":0.45,"cut_depth":0.5}'
                )
            },
            request=httpx.Request("POST", "https://api.openai.com/v1/responses"),
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    agent = build_agent("gpt-5.5", seed=1)

    agent.act(_observation())

    instructions = captured["json"]["instructions"]
    assert "DönerBench Agent Prompt" in instructions
    assert "This is a benchmark, not a chat" in instructions
    assert "`doner_rotation_speed`" in instructions


def test_local_agent_bad_response_degrades_instead_of_aborting(monkeypatch) -> None:
    monkeypatch.setenv("LOCAL_LLM_QWEN_BASE_URL", "http://localhost:9001/v1")

    def fake_post(url, headers, json, timeout):
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": None}}]},
            request=httpx.Request("POST", "http://localhost:9001/v1/chat/completions"),
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    agent = build_agent("qwen3.6", seed=1)

    # A bad response no longer raises: the agent falls back to a safe action and
    # records the failure in its decision trace so the run can continue.
    action = agent.act(_observation())

    assert 0.2 <= action.doner_rotation_speed <= 3.0
    assert agent.last_decision_trace["mode"] == "live_error"
    assert "non-text or empty model output" in str(agent.last_decision_trace["error"])
    assert "qwen3.6" in str(agent.last_decision_trace["error"])

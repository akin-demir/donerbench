from __future__ import annotations

import json
import logging
import math
import os
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import httpx

from donerbench.schemas import (
    CUT_DEPTH_MAX_MM,
    INWARD_PRESSURE_MAX_N,
    KNIFE_VELOCITY_MAX_CM_S,
    VIBRATION_AMPLITUDE_MAX_MM,
    AgentAction,
    AgentInfo,
    Observation,
)

logger = logging.getLogger("donerbench.agents")
PROMPT_PATH = Path(__file__).with_name("prompt.md")


@dataclass(frozen=True)
class AgentRuntimeConfig:
    api_keys: dict[str, str | None] = field(default_factory=dict)
    base_urls: dict[str, str | None] = field(default_factory=dict)
    metadata: dict[str, str | float] = field(default_factory=dict)

    def api_key(self, env_name: str) -> str | None:
        return self.api_keys.get(env_name)

    def base_url(self, env_name: str) -> str | None:
        return self.base_urls.get(env_name)


class Agent(ABC):
    id: str
    name: str
    description: str

    def __init__(self, seed: int, config: AgentRuntimeConfig | None = None) -> None:
        self.rng = random.Random(seed)
        self.config = config or AgentRuntimeConfig()
        self.last_decision_trace: dict[str, object] = {}

    @abstractmethod
    def act(self, observation: Observation) -> AgentAction:
        raise NotImplementedError

    def info(
        self,
        requires_api_key: bool = False,
        api_key_env: str | None = None,
        api_key_configured: bool = True,
    ) -> AgentInfo:
        return AgentInfo(
            id=self.id,
            name=self.name,
            description=self.description,
            requires_api_key=requires_api_key,
            api_key_env=api_key_env,
            api_key_configured=api_key_configured,
        )


class HostedModelAgent(Agent):
    id = "hosted-model"
    name = "HostedModelAgent"
    description = "Provider-backed model agent configured from the registry."

    def __init__(self, seed: int, config: AgentRuntimeConfig | None = None) -> None:
        super().__init__(seed=seed, config=config)
        self.id = str(self.config.metadata.get("id", self.id))
        self.name = str(self.config.metadata.get("name", self.name))
        self.description = str(self.config.metadata.get("description", self.description))
        self.style = str(self.config.metadata.get("style", "adaptive"))
        self.provider = str(self.config.metadata.get("provider", "local"))
        self.model = str(self.config.metadata.get("model", self.id))
        self.base_url = str(self.config.metadata.get("base_url", "")).rstrip("/")
        self.agent_mode = os.getenv("DONERBENCH_AGENT_MODE", "live").lower()
        self.last_live_error: str | None = None
        self.last_valid_action: AgentAction | None = None

    def act(self, observation: Observation) -> AgentAction:
        if self.agent_mode != "profile":
            return self._live_action(observation)
        return self._profile_action(observation)

    def _profile_action(self, observation: Observation) -> AgentAction:
        if self.style == "precision":
            action = self._precision_action(observation)
        elif self.style == "reasoning":
            action = self._reasoning_action(observation)
        elif self.style == "throughput":
            action = self._throughput_action(observation)
        else:
            action = self._adaptive_action(observation)
        self.last_decision_trace = {
            "mode": "profile",
            "provider": self.provider,
            "model": self.model,
            "received_history_items": len(observation.action_history),
            "received_previous_slices": len(observation.previous_slice_metrics),
            "action": action.model_dump(),
        }
        return action

    def _live_action(self, observation: Observation) -> AgentAction:
        payload = self._observation_payload(observation)
        self._log_llm_request(payload)
        # Try once, retry once, then fall back to the last good action (or a safe
        # default) so a single bad response never aborts the whole benchmark.
        last_error: Exception | None = None
        for attempt in range(2):
            try:
                action = self._request_action(payload)
                self.last_valid_action = action
                self.last_decision_trace = {
                    "mode": "live",
                    "provider": self.provider,
                    "model": self.model,
                    "base_url": self.base_url,
                    "received_history_items": len(observation.action_history),
                    "received_previous_slices": len(observation.previous_slice_metrics),
                    "request_payload": _payload_summary(payload),
                    "action": action.model_dump(),
                }
                return action
            except Exception as exc:  # noqa: BLE001 - degrade instead of aborting the run
                last_error = exc
                logger.warning(
                    "LLM action failed agent=%s provider=%s model=%s attempt=%s error=%s",
                    self.id,
                    self.provider,
                    self.model,
                    attempt + 1,
                    exc,
                )

        return self._fallback_action(observation, last_error)

    def _request_action(self, payload: dict[str, object]) -> AgentAction:
        if self.provider == "anthropic":
            raw_action, raw_response = self._call_anthropic(payload)
        elif self.provider == "openai":
            raw_action, raw_response = self._call_openai_responses(payload)
        else:
            raw_action, raw_response = self._call_openai_compatible(payload)
        action = AgentAction.model_validate(raw_action)
        self._log_llm_response(raw_response, action)
        return action

    def _fallback_action(
        self, observation: Observation, error: Exception | None
    ) -> AgentAction:
        reused = self.last_valid_action is not None
        action = self.last_valid_action or self._adaptive_action(observation)
        self.last_valid_action = action
        self.last_decision_trace = {
            "mode": "live_error",
            "provider": self.provider,
            "model": self.model,
            "base_url": self.base_url,
            "error": str(error) if error else "unknown error",
            "reused_last_valid_action": reused,
            "action": action.model_dump(),
        }
        return action

    def _log_llm_request(self, payload: dict[str, object]) -> None:
        logger.info(
            "LLM request agent=%s provider=%s model=%s base_url=%s history_items=%s previous_slices=%s attempts_remaining=%s",
            self.id,
            self.provider,
            self.model,
            self.base_url,
            len(payload.get("action_history", [])),
            len(payload.get("previous_slice_metrics", [])),
            payload.get("attempts_remaining"),
        )
        if _log_payloads_enabled():
            logger.info(
                "LLM request payload agent=%s payload=%s",
                self.id,
                json.dumps(_redact(payload), ensure_ascii=False, default=str),
            )

    def _log_llm_response(self, raw_response: str, action: AgentAction) -> None:
        logger.info(
            "LLM response agent=%s provider=%s model=%s action=%s",
            self.id,
            self.provider,
            self.model,
            action.model_dump(),
        )
        if _log_payloads_enabled():
            logger.info("LLM raw response agent=%s response=%s", self.id, raw_response[:4000])

    def _call_openai_responses(self, payload: dict[str, object]) -> tuple[dict[str, object], str]:
        if not self.base_url:
            raise RuntimeError(f"{self.id} has no base_url configured")
        api_key = self._configured_api_key()
        if not api_key:
            raise RuntimeError(f"{self.id} requires an OpenAI API key")

        request_body = {
            "model": self.model,
            "instructions": self._system_prompt(),
            "input": json.dumps(payload, separators=(",", ":")),
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "donerbench_action",
                    "strict": True,
                    "schema": self._action_json_schema(),
                }
            },
        }
        response = httpx.post(
            f"{self.base_url}/responses",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            json=request_body,
            timeout=_llm_timeout_seconds(),
        )
        self._raise_for_bad_response(response)
        content = self._extract_openai_response_text(response.json())
        return self._parse_action_content(content), content

    def _call_openai_compatible(self, payload: dict[str, object]) -> tuple[dict[str, object], str]:
        if not self.base_url:
            raise RuntimeError(f"{self.id} has no base_url configured")
        headers = {"Content-Type": "application/json"}
        api_key = self._configured_api_key()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        response = httpx.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json={
                "model": self.model,
                "temperature": 0,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": self._system_prompt()},
                    {"role": "user", "content": json.dumps(payload, separators=(",", ":"))},
                ],
            },
            timeout=_llm_timeout_seconds(),
        )
        self._raise_for_bad_response(response)
        content = _require_text_response(
            response.json()["choices"][0]["message"].get("content"),
            agent_id=self.id,
            provider=self.provider,
            model=self.model,
        )
        return self._parse_action_content(content), content

    def _call_anthropic(self, payload: dict[str, object]) -> tuple[dict[str, object], str]:
        api_key = self._configured_api_key()
        if not api_key:
            raise RuntimeError(f"{self.id} requires an Anthropic API key")
        if not self.base_url:
            raise RuntimeError(f"{self.id} has no base_url configured")

        response = httpx.post(
            f"{self.base_url}/messages",
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": self.model,
                "max_tokens": 450,
                "temperature": 0,
                "system": self._system_prompt(),
                "messages": [
                    {"role": "user", "content": json.dumps(payload, separators=(",", ":"))}
                ],
            },
            timeout=_llm_timeout_seconds(),
        )
        self._raise_for_bad_response(response)
        parts = response.json().get("content", [])
        content = "".join(
            part["text"]
            for part in parts
            if isinstance(part, dict)
            and part.get("type") == "text"
            and isinstance(part.get("text"), str)
        )
        content = _require_text_response(
            content,
            agent_id=self.id,
            provider=self.provider,
            model=self.model,
        )
        return self._parse_action_content(content), content

    def _raise_for_bad_response(self, response: httpx.Response) -> None:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            body = response.text[:2000]
            logger.error(
                "LLM error agent=%s provider=%s model=%s status=%s body=%s",
                self.id,
                self.provider,
                self.model,
                response.status_code,
                body,
            )
            raise RuntimeError(
                f"{self.id} model call failed with HTTP {response.status_code}: {body}"
            ) from exc

    def _extract_openai_response_text(self, data: dict[str, object]) -> str:
        output_text = data.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text
        chunks: list[str] = []
        output = data.get("output", [])
        if isinstance(output, list):
            for item in output:
                if not isinstance(item, dict):
                    continue
                content = item.get("content", [])
                if not isinstance(content, list):
                    continue
                for part in content:
                    if isinstance(part, dict):
                        text = part.get("text")
                        if isinstance(text, str):
                            chunks.append(text)
        if chunks:
            return "".join(chunks)
        raise ValueError(f"{self.id} OpenAI response did not contain output text")

    def _configured_api_key(self) -> str | None:
        for value in self.config.api_keys.values():
            if value:
                return value
        return None

    def _parse_action_content(self, content: object) -> dict[str, object]:
        content = _require_text_response(
            content,
            agent_id=self.id,
            provider=self.provider,
            model=self.model,
        )
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            cleaned = cleaned.removeprefix("json").strip()
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1:
            raise ValueError(f"{self.id} did not return a JSON object")
        return json.loads(cleaned[start : end + 1])

    def _system_prompt(self) -> str:
        return _benchmark_prompt()

    def _action_json_schema(self) -> dict[str, object]:
        number = {"type": "number"}
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "doner_rotation_speed": number,
                "heat_temperature": number,
                "knife_angle": number,
                "knife_velocity": number,
                "inward_pressure": number,
                "vibration_frequency": number,
                "vibration_amplitude": number,
                "cut_location_from_top": number,
                "cut_depth": number,
            },
            "required": [
                "doner_rotation_speed",
                "heat_temperature",
                "knife_angle",
                "knife_velocity",
                "inward_pressure",
                "vibration_frequency",
                "vibration_amplitude",
                "cut_location_from_top",
                "cut_depth",
            ],
        }

    def _observation_payload(self, observation: Observation) -> dict[str, object]:
        return {
            "agent_id": self.id,
            "model": self.model,
            "attempts_remaining": int(observation.time_remaining),
            "attempt_number": len(observation.action_history) + 1,
            "doner_rotation_angle": round(observation.doner_rotation_angle, 4),
            "doner_rotation_speed": round(observation.doner_rotation_speed, 3),
            "heat_temperature": round(observation.heat_temperature, 2),
            "current_surface_geometry": observation.current_surface_geometry,
            "current_surface_freshness": round(observation.current_surface_freshness, 2),
            "current_surface_cookedness": round(observation.current_surface_cookedness, 2),
            "knife_state": observation.knife_state.model_dump(),
            # Full record of this run so the model can reason over every past attempt.
            "previous_slice_metrics": [
                slice_.model_dump(exclude={"operation_log"})
                for slice_ in observation.previous_slice_metrics
            ],
            "action_history": [
                result.model_dump(
                    exclude={
                        "agent_trace": True,
                        "slice_metrics": {"operation_log": True},
                    }
                )
                for result in observation.action_history
            ],
            "objective": (
                "You get a fixed number of slice attempts. Use the record of your past "
                "attempts to make each next slice better: thin and consistent, fresh, "
                "properly cooked, with low tearing and low waste."
            ),
        }

    def _reasoning_action(self, observation: Observation) -> AgentAction:
        heat_correction = (observation.current_surface_cookedness - 76.0) / 100.0
        timing_wave = math.sin(observation.doner_rotation_angle * 1.8)
        return AgentAction(
            doner_rotation_speed=0.82 + timing_wave * 0.08,
            heat_temperature=190.0 - heat_correction * 18.0,
            knife_angle=11.0 + timing_wave * 2.4,
            knife_velocity=(0.5 + self.rng.uniform(-0.025, 0.025)) * KNIFE_VELOCITY_MAX_CM_S,
            inward_pressure=(0.46 + heat_correction * 0.1 + self.rng.uniform(-0.025, 0.025))
            * INWARD_PRESSURE_MAX_N,
            vibration_frequency=34.0,
            vibration_amplitude=0.36 * VIBRATION_AMPLITUDE_MAX_MM,
            cut_location_from_top=0.43 + self.rng.uniform(-0.04, 0.04),
            cut_depth=(0.49 + heat_correction * 0.04 + self.rng.uniform(-0.025, 0.025))
            * CUT_DEPTH_MAX_MM,
        )

    def _precision_action(self, observation: Observation) -> AgentAction:
        freshness_bias = (observation.current_surface_freshness - 80.0) / 100.0
        return AgentAction(
            doner_rotation_speed=0.68 + math.sin(observation.doner_rotation_angle * 0.8) * 0.05,
            heat_temperature=178.0 + freshness_bias * 16.0,
            knife_angle=9.0 + math.sin(observation.doner_rotation_angle) * 2.0,
            knife_velocity=(0.42 + freshness_bias * 0.06 + self.rng.uniform(-0.02, 0.02))
            * KNIFE_VELOCITY_MAX_CM_S,
            inward_pressure=(0.37 + self.rng.uniform(-0.025, 0.025)) * INWARD_PRESSURE_MAX_N,
            vibration_frequency=28.0,
            vibration_amplitude=0.28 * VIBRATION_AMPLITUDE_MAX_MM,
            cut_location_from_top=0.45 + self.rng.uniform(-0.035, 0.035),
            cut_depth=(0.39 + self.rng.uniform(-0.025, 0.025)) * CUT_DEPTH_MAX_MM,
        )

    def _throughput_action(self, observation: Observation) -> AgentAction:
        cooked_bias = (observation.current_surface_cookedness - 70.0) / 100.0
        return AgentAction(
            doner_rotation_speed=1.05 + self.rng.uniform(-0.08, 0.08),
            heat_temperature=202.0 - cooked_bias * 10.0,
            knife_angle=15.0 + self.rng.uniform(-4.0, 4.0),
            knife_velocity=(0.66 + self.rng.uniform(-0.045, 0.045)) * KNIFE_VELOCITY_MAX_CM_S,
            inward_pressure=(0.58 + cooked_bias * 0.08 + self.rng.uniform(-0.04, 0.04))
            * INWARD_PRESSURE_MAX_N,
            vibration_frequency=38.0,
            vibration_amplitude=0.42 * VIBRATION_AMPLITUDE_MAX_MM,
            cut_location_from_top=0.42 + self.rng.uniform(-0.07, 0.07),
            cut_depth=(0.58 + self.rng.uniform(-0.045, 0.045)) * CUT_DEPTH_MAX_MM,
        )

    def _adaptive_action(self, observation: Observation) -> AgentAction:
        cooked_bias = (observation.current_surface_cookedness - 72.0) / 100.0
        return AgentAction(
            doner_rotation_speed=0.82 + math.sin(observation.doner_rotation_angle * 0.9) * 0.07,
            heat_temperature=186.0 - cooked_bias * 12.0,
            knife_angle=12.0 + math.sin(observation.doner_rotation_angle * 1.2) * 2.6,
            knife_velocity=(0.54 + self.rng.uniform(-0.03, 0.03)) * KNIFE_VELOCITY_MAX_CM_S,
            inward_pressure=(0.48 + cooked_bias * 0.08 + self.rng.uniform(-0.03, 0.03))
            * INWARD_PRESSURE_MAX_N,
            vibration_frequency=32.0,
            vibration_amplitude=0.33 * VIBRATION_AMPLITUDE_MAX_MM,
            cut_location_from_top=0.44 + self.rng.uniform(-0.045, 0.045),
            cut_depth=(0.5 + self.rng.uniform(-0.03, 0.03)) * CUT_DEPTH_MAX_MM,
        )


def _log_payloads_enabled() -> bool:
    return os.getenv("DONERBENCH_LOG_LLM_PAYLOADS", "").lower() in {"1", "true", "yes", "on"}


@lru_cache(maxsize=1)
def _benchmark_prompt() -> str:
    try:
        return PROMPT_PATH.read_text(encoding="utf-8").strip()
    except OSError:
        logger.warning("Benchmark prompt file missing at %s; using fallback prompt", PROMPT_PATH)
        return (
            "You are an AI agent controlling a döner slicing benchmark. "
            "Return exactly one JSON object and no prose. "
            "Choose numeric fields within bounds for rotation, heat, knife angle, "
            "velocity, pressure, vibration, cut location, and cut depth. "
            "Use action_history and previous_slice_metrics to improve the next cut."
        )


def _require_text_response(
    value: object,
    *,
    agent_id: str,
    provider: str,
    model: str,
) -> str:
    if isinstance(value, str) and value.strip():
        return value
    raise ValueError(
        f"{agent_id} returned non-text or empty model output "
        f"(provider={provider}, model={model}, type={type(value).__name__})"
    )


def _llm_timeout_seconds() -> float:
    value = os.getenv("DONERBENCH_LLM_TIMEOUT_SECONDS", "120")
    try:
        return max(5.0, float(value))
    except ValueError:
        return 120.0


def _payload_summary(payload: dict[str, object]) -> dict[str, object]:
    return {
        "attempts_remaining": payload.get("attempts_remaining"),
        "doner_rotation_angle": payload.get("doner_rotation_angle"),
        "doner_rotation_speed": payload.get("doner_rotation_speed"),
        "heat_temperature": payload.get("heat_temperature"),
        "history_items": len(payload.get("action_history", [])),
        "previous_slices": len(payload.get("previous_slice_metrics", [])),
    }


def _redact(value):
    if isinstance(value, dict):
        return {
            key: "***REDACTED***" if "key" in key.lower() or "token" in key.lower() else _redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value

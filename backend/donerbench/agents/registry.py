from __future__ import annotations

import os
from dataclasses import dataclass

from donerbench.agents.base import (
    Agent,
    AgentRuntimeConfig,
    HostedModelAgent,
)
from donerbench.schemas import AgentInfo


@dataclass(frozen=True)
class AgentDefinition:
    id: str
    agent_type: type[Agent]
    name: str | None = None
    description: str | None = None
    provider: str = "builtin"
    model: str | None = None
    base_url: str | None = None
    base_url_env: str | None = None
    api_key_env: str | None = None
    style: str = "adaptive"

    @property
    def requires_api_key(self) -> bool:
        return self.api_key_env is not None


# This is the source of truth for agents the app can offer.
# Add hosted or local LLM-backed agents here.
AGENT_DEFINITIONS: dict[str, AgentDefinition] = {
    "gpt-5.5": AgentDefinition(
        id="gpt-5.5",
        agent_type=HostedModelAgent,
        name="GPT-5.5",
        description="OpenAI-hosted reasoning model agent profile.",
        provider="openai",
        # Override with OPENAI_MODEL to match whatever your account actually serves.
        model=os.getenv("OPENAI_MODEL", "gpt-5.5"),
        base_url="https://api.openai.com/v1",
        api_key_env="OPENAI_API_KEY",
        style="reasoning",
    ),
    "claude-sonnet-4.6": AgentDefinition(
        id="claude-sonnet-4.6",
        agent_type=HostedModelAgent,
        name="Claude Sonnet 4.6",
        description="Anthropic-hosted speed/intelligence agent profile.",
        provider="anthropic",
        model="claude-sonnet-4-6",
        base_url="https://api.anthropic.com/v1",
        api_key_env="ANTHROPIC_API_KEY",
        style="adaptive",
    ),
    "claude-opus-4.6": AgentDefinition(
        id="claude-opus-4.6",
        agent_type=HostedModelAgent,
        name="Claude Opus 4.6",
        description="Anthropic-hosted deep reasoning agent profile.",
        provider="anthropic",
        model="claude-opus-4-6",
        base_url="https://api.anthropic.com/v1",
        api_key_env="ANTHROPIC_API_KEY",
        style="precision",
    ),
    "qwen3.6": AgentDefinition(
        id="qwen3.6",
        agent_type=HostedModelAgent,
        name="Qwen3.6",
        description="OpenAI-compatible local model endpoint, such as Ollama or LM Studio.",
        provider="local",
        model="cyankiwi/Qwen3-VL-32B-Instruct-AWQ-4bit",
        # No hardcoded default: set LOCAL_LLM_QWEN_BASE_URL to enable this agent.
        base_url_env="LOCAL_LLM_QWEN_BASE_URL",
        style="throughput",
    ),
    "gemma-4-2b": AgentDefinition(
        id="gemma-4-2b",
        agent_type=HostedModelAgent,
        name="Gemma-4-2b",
        description="OpenAI-compatible local model endpoint, such as Ollama or LM Studio.",
        provider="local",
        model="google/gemma-4-E2B-it",
        # No hardcoded default: set LOCAL_LLM_GEMMA_BASE_URL to enable this agent.
        base_url_env="LOCAL_LLM_GEMMA_BASE_URL",
        style="throughput",
    ),
}


def available_agents() -> dict[str, AgentDefinition]:
    return AGENT_DEFINITIONS.copy()


def build_agent(agent_id: str, seed: int) -> Agent:
    definitions = available_agents()
    try:
        definition = definitions[agent_id]
    except KeyError as exc:
        known = ", ".join(sorted(definitions))
        raise ValueError(f"Unknown agent '{agent_id}'. Known agents: {known}") from exc

    config = runtime_config_for(definition)
    if definition.api_key_env and not config.api_key(definition.api_key_env):
        raise ValueError(
            f"Agent '{agent_id}' requires {definition.api_key_env}; set it in your environment."
        )
    if not _endpoint_configured(definition):
        raise ValueError(
            f"Agent '{agent_id}' has no endpoint configured; "
            f"set {definition.base_url_env} in your environment."
        )
    return definition.agent_type(seed=seed, config=config)


def list_agents() -> list[AgentInfo]:
    infos: list[AgentInfo] = []
    for definition in available_agents().values():
        agent = definition.agent_type(seed=0, config=runtime_config_for(definition))
        infos.append(
            AgentInfo(
                id=agent.id,
                name=definition.name or agent.name,
                description=definition.description or agent.description,
                provider=definition.provider,
                model=definition.model,
                base_url=resolved_base_url(definition),
                base_url_env=definition.base_url_env,
                requires_api_key=definition.requires_api_key,
                api_key_env=definition.api_key_env,
                api_key_configured=_api_key_configured(definition),
                endpoint_configured=_endpoint_configured(definition),
            )
        )
    return infos


def _endpoint_configured(definition: AgentDefinition) -> bool:
    # builtin agents need no endpoint; hosted/local agents need a resolvable base_url.
    if definition.provider == "builtin":
        return True
    return bool(resolved_base_url(definition))


def runtime_config_for(definition: AgentDefinition) -> AgentRuntimeConfig:
    api_keys: dict[str, str | None] = {}
    if definition.api_key_env:
        api_keys[definition.api_key_env] = os.getenv(definition.api_key_env)
    base_urls: dict[str, str | None] = {}
    if definition.base_url_env:
        base_urls[definition.base_url_env] = os.getenv(definition.base_url_env)
    metadata: dict[str, str | float] = {
        "id": definition.id,
        "name": definition.name or definition.id,
        "description": definition.description or "",
        "provider": definition.provider,
        "model": definition.model or "",
        "base_url": resolved_base_url(definition) or "",
        "style": definition.style,
    }
    return AgentRuntimeConfig(api_keys=api_keys, base_urls=base_urls, metadata=metadata)


def _api_key_configured(definition: AgentDefinition) -> bool:
    return not definition.api_key_env or bool(os.getenv(definition.api_key_env))


def resolved_base_url(definition: AgentDefinition) -> str | None:
    if definition.base_url_env and os.getenv(definition.base_url_env):
        return os.getenv(definition.base_url_env)
    return definition.base_url

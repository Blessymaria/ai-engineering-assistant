"""Provider interface so the model can be swapped without touching the agent."""

from dataclasses import dataclass, field
from typing import Protocol


class LLMError(RuntimeError):
    """The model could not be reached or returned something unusable."""


@dataclass
class ToolCallRequest:
    name: str
    arguments: dict


@dataclass
class LLMReply:
    content: str
    tool_calls: list[ToolCallRequest] = field(default_factory=list)
    tokens: int = 0
    seconds: float = 0.0
    prompt_tokens: int = 0  # how much of the prompt the model processed (for spotting context limits)
    done_reason: str | None = None  # "stop", or "length" when the reply was cut off


class LLMProvider(Protocol):
    name: str

    def chat(self, messages: list[dict], tools: list[dict] | None = None, max_tokens: int = 1024,
             json_schema: dict | None = None) -> LLMReply:
        """messages use the Ollama/OpenAI chat format; tools are function schemas;
        json_schema forces the reply content to be JSON matching it."""
        ...

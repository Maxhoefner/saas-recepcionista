from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TypedDict


class ChatRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ToolSpec(TypedDict):
    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass
class ToolCallRequest:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ChatMessage:
    """Provider-agnostic message. `tool_calls` is set only on an ASSISTANT
    message that requested tools; `tool_call_id`/`tool_name` only on a TOOL
    message answering one of those requests."""

    role: ChatRole
    content: str | None = None
    tool_calls: list[ToolCallRequest] = field(default_factory=list)
    tool_call_id: str | None = None
    tool_name: str | None = None


@dataclass
class AgentTurnResult:
    text: str | None
    tool_calls: list[ToolCallRequest]


class LLMProvider(ABC):
    """Abstraction over a specific LLM vendor's API. The rest of the app
    (agent loop, conversation history, tool execution) never imports a
    provider SDK directly — only this interface — so swapping models or
    adding a second provider doesn't touch agent logic."""

    @abstractmethod
    async def generate(
        self, *, system: str, messages: list[ChatMessage], tools: list[ToolSpec]
    ) -> AgentTurnResult: ...

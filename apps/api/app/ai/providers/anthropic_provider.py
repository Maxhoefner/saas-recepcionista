from typing import Any, cast

from anthropic import AsyncAnthropic

from app.ai.providers.base import (
    AgentTurnResult,
    ChatMessage,
    ChatRole,
    LLMProvider,
    ToolCallRequest,
    ToolSpec,
)


def _to_anthropic_messages(messages: list[ChatMessage]) -> list[dict[str, Any]]:
    """Translate our provider-agnostic history into Anthropic's block format.

    Anthropic expects every tool_use in an assistant turn to be answered by a
    tool_result in the *next* user message — so consecutive TOOL messages
    (one per tool call in that turn) get coalesced into a single user turn.
    """
    result: list[dict[str, Any]] = []
    pending_tool_results: list[dict[str, Any]] = []

    def flush_tool_results() -> None:
        if pending_tool_results:
            result.append({"role": "user", "content": list(pending_tool_results)})
            pending_tool_results.clear()

    for message in messages:
        if message.role == ChatRole.TOOL:
            pending_tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": message.tool_call_id,
                    "content": message.content or "",
                }
            )
            continue

        flush_tool_results()

        if message.role == ChatRole.USER:
            result.append({"role": "user", "content": message.content or ""})
        else:  # ASSISTANT
            blocks: list[dict[str, Any]] = []
            if message.content:
                blocks.append({"type": "text", "text": message.content})
            for tool_call in message.tool_calls:
                blocks.append(
                    {
                        "type": "tool_use",
                        "id": tool_call.id,
                        "name": tool_call.name,
                        "input": tool_call.arguments,
                    }
                )
            result.append({"role": "assistant", "content": blocks})

    flush_tool_results()
    return result


class AnthropicProvider(LLMProvider):
    def __init__(self, *, api_key: str, model: str, max_tokens: int = 1024) -> None:
        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens

    async def generate(
        self, *, system: str, messages: list[ChatMessage], tools: list[ToolSpec]
    ) -> AgentTurnResult:
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=system,
            # Both params are plain dicts built to match the SDK's expected
            # shape at runtime — cast rather than fight mypy over its very
            # large generated TypedDict unions for messages/tools.
            messages=cast(Any, _to_anthropic_messages(messages)),
            tools=cast(Any, [dict(tool) for tool in tools]),
        )

        text_parts: list[str] = []
        tool_calls: list[ToolCallRequest] = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCallRequest(id=block.id, name=block.name, arguments=dict(block.input))
                )

        return AgentTurnResult(text="".join(text_parts) or None, tool_calls=tool_calls)

import json
import logging
import time
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.prompts.system_prompt import build_system_prompt
from app.ai.providers.base import ChatMessage, ChatRole, LLMProvider, ToolCallRequest
from app.ai.tools import TOOL_REGISTRY, ToolContext
from app.core.config import get_settings
from app.models.ai_tool_call import AIToolCall
from app.models.business import Business
from app.models.conversation import Conversation, ConversationStatus
from app.models.message import Message, MessageRole
from app.services import ai_settings_service, conversation_service

logger = logging.getLogger(__name__)
settings = get_settings()

# After one of these tools runs, stop the loop even if the model would keep
# going — a handoff means a human takes it from here, not the AI.
_TERMINAL_TOOLS = {"create_handoff"}

_FALLBACK_REPLY = "Disculpá, estoy teniendo un problema para resolver esto. Un momento, por favor."
_HANDOFF_REPLY = "Listo, te voy a comunicar con alguien del equipo."
_EMPTY_REPLY = "¿En qué más te puedo ayudar?"


def _history_to_chat_messages(messages: list[Message]) -> list[ChatMessage]:
    chat_messages = []
    for m in messages:
        extra = m.extra or {}
        if m.role == MessageRole.USER:
            chat_messages.append(ChatMessage(role=ChatRole.USER, content=m.content))
        elif m.role == MessageRole.ASSISTANT:
            tool_calls = [
                ToolCallRequest(id=tc["id"], name=tc["name"], arguments=tc["arguments"])
                for tc in extra.get("tool_calls", [])
            ]
            chat_messages.append(
                ChatMessage(role=ChatRole.ASSISTANT, content=m.content, tool_calls=tool_calls)
            )
        elif m.role == MessageRole.TOOL:
            chat_messages.append(
                ChatMessage(
                    role=ChatRole.TOOL,
                    content=m.content,
                    tool_call_id=extra.get("tool_call_id"),
                    tool_name=extra.get("tool_name"),
                )
            )
        # SYSTEM messages aren't replayed — the system prompt is rebuilt fresh every turn.
    return chat_messages


async def _execute_tool(
    ctx: ToolContext, tool_call: ToolCallRequest, message_id: uuid.UUID
) -> dict:
    tool = TOOL_REGISTRY.get(tool_call.name)
    start = time.monotonic()
    if tool is None:
        result: dict = {"error": f"Tool desconocida: {tool_call.name}"}
        success = False
    else:
        try:
            args = tool.args_model.model_validate(tool_call.arguments)
            result = await tool.handler(ctx, args)
            success = "error" not in result
        except Exception:
            logger.exception("Tool %s failed", tool_call.name)
            result = {"error": "Ocurrió un problema interno al ejecutar esa acción."}
            success = False

    latency_ms = int((time.monotonic() - start) * 1000)
    ctx.db.add(
        AIToolCall(
            message_id=message_id,
            tool_name=tool_call.name,
            arguments=tool_call.arguments,
            result=result,
            success=success,
            latency_ms=latency_ms,
        )
    )
    return result


async def _run_agent_loop(
    db: AsyncSession, *, business_id: uuid.UUID, conversation: Conversation, provider: LLMProvider
) -> Message:
    """Runs the tool-calling loop and returns the Message that was actually
    given back to the customer — guaranteed to exist and have text, even on
    a handoff or a loop that ran out of iterations."""
    business = await db.get(Business, business_id)
    assert business is not None
    ai_settings = await ai_settings_service.get_or_create_ai_settings(db, business_id=business_id)

    history = await conversation_service.list_messages(
        db, business_id=business_id, conversation_id=conversation.id
    )
    # Sliding window to control token cost — summarizing older turns is a
    # later refinement, not needed at MVP conversation lengths/volume.
    chat_history = _history_to_chat_messages(history[-30:])

    now_local = datetime.now(ZoneInfo(business.timezone))
    system_prompt = build_system_prompt(
        business=business, ai_settings=ai_settings, now_local=now_local
    )
    tool_specs = [tool.to_spec() for tool in TOOL_REGISTRY.values()]
    ctx = ToolContext(db=db, business_id=business_id, conversation=conversation)

    for _ in range(settings.AGENT_MAX_TOOL_ITERATIONS):
        result = await provider.generate(
            system=system_prompt, messages=chat_history, tools=tool_specs
        )

        tool_calls_extra = (
            {
                "tool_calls": [
                    {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                    for tc in result.tool_calls
                ]
            }
            if result.tool_calls
            else None
        )
        assistant_message = await conversation_service.append_message(
            db,
            conversation_id=conversation.id,
            role=MessageRole.ASSISTANT,
            content=result.text,
            extra=tool_calls_extra,
        )
        chat_history.append(
            ChatMessage(role=ChatRole.ASSISTANT, content=result.text, tool_calls=result.tool_calls)
        )

        if not result.tool_calls:
            assistant_message.content = assistant_message.content or _EMPTY_REPLY
            await db.commit()
            await db.refresh(assistant_message)
            return assistant_message

        handoff_triggered = False
        for tool_call in result.tool_calls:
            tool_result = await _execute_tool(ctx, tool_call, assistant_message.id)
            if tool_call.name in _TERMINAL_TOOLS and "error" not in tool_result:
                handoff_triggered = True

            content = json.dumps(tool_result, ensure_ascii=False, default=str)
            await conversation_service.append_message(
                db,
                conversation_id=conversation.id,
                role=MessageRole.TOOL,
                content=content,
                extra={"tool_call_id": tool_call.id, "tool_name": tool_call.name},
            )
            chat_history.append(
                ChatMessage(
                    role=ChatRole.TOOL,
                    content=content,
                    tool_call_id=tool_call.id,
                    tool_name=tool_call.name,
                )
            )
        await db.commit()

        if handoff_triggered:
            assistant_message.content = assistant_message.content or _HANDOFF_REPLY
            await db.commit()
            await db.refresh(assistant_message)
            return assistant_message

    fallback_message = await conversation_service.append_message(
        db, conversation_id=conversation.id, role=MessageRole.ASSISTANT, content=_FALLBACK_REPLY
    )
    await db.commit()
    await db.refresh(fallback_message)
    return fallback_message


async def handle_message(
    db: AsyncSession,
    *,
    business_id: uuid.UUID,
    conversation: Conversation,
    user_text: str,
    provider: LLMProvider,
    whatsapp_message_id: str | None = None,
) -> tuple[Message, Message | None]:
    """Appends the customer's message and, unless a human already took over
    this conversation, runs the agent. Returns (customer_message, reply) —
    `reply` is None when the conversation is in HUMAN_HANDOFF/CLOSED, since
    nothing should auto-reply in that case.

    `whatsapp_message_id`, when given, is stored on the same INSERT as the
    message — its unique constraint is what actually closes the race if
    Meta redelivers the same webhook event concurrently (raises
    IntegrityError on the `await db.commit()` a few lines down; the caller
    is expected to catch that and treat it as "already processed")."""
    user_message = await conversation_service.append_message(
        db,
        conversation_id=conversation.id,
        role=MessageRole.USER,
        content=user_text,
        whatsapp_message_id=whatsapp_message_id,
    )
    conversation_service.touch(conversation)
    await db.commit()
    await db.refresh(user_message)

    if conversation.status != ConversationStatus.AI_ACTIVE:
        return user_message, None

    try:
        reply = await _run_agent_loop(
            db, business_id=business_id, conversation=conversation, provider=provider
        )
    except Exception:
        logger.exception("Agent loop failed for conversation %s", conversation.id)
        reply = await conversation_service.append_message(
            db, conversation_id=conversation.id, role=MessageRole.ASSISTANT, content=_FALLBACK_REPLY
        )
        await db.commit()
        await db.refresh(reply)

    return user_message, reply

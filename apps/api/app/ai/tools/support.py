from pydantic import BaseModel, Field

from app.ai.tools.base import NoArgs, ToolContext, ToolDefinition
from app.models.conversation import ConversationStatus
from app.services import conversation_service, faq_service


async def get_faq(ctx: ToolContext, _: NoArgs) -> dict:
    faqs = await faq_service.list_faqs(ctx.db, business_id=ctx.business_id, active_only=True)
    return {"faqs": [{"question": f.question, "answer": f.answer} for f in faqs]}


class HandoffArgs(BaseModel):
    reason: str | None = Field(default=None, description="Por qué se deriva a un humano")


async def create_handoff(ctx: ToolContext, args: HandoffArgs) -> dict:
    await conversation_service.set_status(
        ctx.db,
        business_id=ctx.business_id,
        conversation_id=ctx.conversation.id,
        status=ConversationStatus.HUMAN_HANDOFF,
    )
    return {"status": "HUMAN_HANDOFF", "reason": args.reason}


TOOLS = [
    ToolDefinition(
        name="get_faq",
        description="Preguntas frecuentes configuradas por el negocio (estacionamiento, mascotas, "
        "políticas, etc.). Usar para cualquier pregunta que no sea sobre servicios/turnos.",
        args_model=NoArgs,
        handler=get_faq,
    ),
    ToolDefinition(
        name="create_handoff",
        description="Deriva la conversación a un humano. Usar cuando el cliente lo pida "
        "explícitamente, o cuando la consulta esté claramente fuera de lo que podés resolver.",
        args_model=HandoffArgs,
        handler=create_handoff,
    ),
]

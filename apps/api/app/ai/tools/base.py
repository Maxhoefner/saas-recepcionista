import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.providers.base import ToolSpec
from app.models.conversation import Conversation


class NoArgs(BaseModel):
    pass


@dataclass
class ToolContext:
    db: AsyncSession
    business_id: uuid.UUID
    conversation: Conversation


# Each concrete handler takes its own specific args model (a BaseModel
# subtype), not BaseModel itself — mypy's contravariant Callable check would
# reject that pairing, so this is intentionally `Any`. Runtime correctness is
# guaranteed by ToolDefinition always validating with its own `args_model`
# before calling `handler` (see agent._execute_tool).
ToolHandler = Callable[[ToolContext, Any], Awaitable[dict[str, Any]]]


@dataclass
class ToolDefinition:
    name: str
    description: str
    args_model: type[BaseModel]
    handler: ToolHandler

    def to_spec(self) -> ToolSpec:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.args_model.model_json_schema(),
        }


def find_by_name(
    items: list, name: str, *, name_attr: str = "name"
) -> tuple[Any | None, str | None]:
    """Case-insensitive name lookup for the entities the AI refers to by name
    (services, professionals) since a customer says "corte", never a UUID.

    Returns (match, error) — error is a short message for ambiguous/missing
    matches, meant to go straight into a tool result for the LLM to read.
    """
    normalized = name.strip().lower()
    exact = [item for item in items if getattr(item, name_attr).lower() == normalized]
    if len(exact) == 1:
        return exact[0], None

    partial = [item for item in items if normalized in getattr(item, name_attr).lower()]
    if len(partial) == 1:
        return partial[0], None
    if len(partial) > 1:
        options = ", ".join(getattr(item, name_attr) for item in partial)
        return None, f"Hay más de una coincidencia para '{name}': {options}. Pedile que aclare."
    return None, f"No se encontró '{name}'."

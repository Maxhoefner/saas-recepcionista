from app.ai.tools import appointments, catalog, support
from app.ai.tools.base import ToolContext, ToolDefinition

TOOL_REGISTRY: dict[str, ToolDefinition] = {
    tool.name: tool for tool in [*catalog.TOOLS, *appointments.TOOLS, *support.TOOLS]
}

__all__ = ["TOOL_REGISTRY", "ToolContext", "ToolDefinition"]

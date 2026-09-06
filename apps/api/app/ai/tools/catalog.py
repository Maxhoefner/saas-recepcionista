from pydantic import BaseModel, Field
from sqlalchemy import select

from app.ai.tools.base import NoArgs, ToolContext, ToolDefinition, find_by_name
from app.models.business import Business
from app.services import catalog_service, schedule_service


async def get_business_info(ctx: ToolContext, _: NoArgs) -> dict:
    business = await ctx.db.scalar(select(Business).where(Business.id == ctx.business_id))
    assert business is not None
    return {
        "name": business.name,
        "phone": business.phone,
        "address": business.address,
        "timezone": business.timezone,
    }


async def get_services(ctx: ToolContext, _: NoArgs) -> dict:
    services = await catalog_service.list_services(ctx.db, business_id=ctx.business_id)
    return {
        "services": [
            {
                "name": s.name,
                "description": s.description,
                "price_cents": s.price_cents,
                "duration_minutes": s.duration_minutes,
            }
            for s in services
            if s.active
        ]
    }


class ServiceNameArgs(BaseModel):
    service_name: str = Field(description="Nombre del servicio tal como lo dijo el cliente")


async def get_service_details(ctx: ToolContext, args: ServiceNameArgs) -> dict:
    all_services = await catalog_service.list_services(ctx.db, business_id=ctx.business_id)
    services = [s for s in all_services if s.active]
    service, error = find_by_name(services, args.service_name)
    if error:
        return {"error": error}
    assert service is not None
    return {
        "name": service.name,
        "description": service.description,
        "price_cents": service.price_cents,
        "duration_minutes": service.duration_minutes,
    }


class ProfessionalsArgs(BaseModel):
    service_name: str | None = Field(
        default=None, description="Si se da, solo lista profesionales que realizan ese servicio"
    )


async def get_professionals(ctx: ToolContext, args: ProfessionalsArgs) -> dict:
    all_professionals = await catalog_service.list_professionals(
        ctx.db, business_id=ctx.business_id
    )
    professionals = [p for p in all_professionals if p.active]
    if args.service_name is None:
        return {"professionals": [p.name for p in professionals]}

    all_services = await catalog_service.list_services(ctx.db, business_id=ctx.business_id)
    services = [s for s in all_services if s.active]
    service, error = find_by_name(services, args.service_name)
    if error:
        return {"error": error}
    assert service is not None

    matching = []
    for professional in professionals:
        info = await catalog_service.professional_to_read_dict(ctx.db, professional)
        if service.id in info["service_ids"]:
            matching.append(professional.name)
    return {"professionals": matching}


async def get_business_hours(ctx: ToolContext, _: NoArgs) -> dict:
    hours = await schedule_service.list_business_hours(ctx.db, business_id=ctx.business_id)
    weekday_names = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    return {
        "hours": [
            {
                "weekday": weekday_names[h.weekday],
                "start_time": h.start_time.isoformat(timespec="minutes"),
                "end_time": h.end_time.isoformat(timespec="minutes"),
            }
            for h in hours
        ]
    }


TOOLS = [
    ToolDefinition(
        name="get_business_info",
        description="Devuelve nombre, teléfono, dirección y timezone del negocio.",
        args_model=NoArgs,
        handler=get_business_info,
    ),
    ToolDefinition(
        name="get_services",
        description="Lista los servicios activos del negocio con precio y duración. "
        "Usar siempre que el cliente pregunte qué servicios hay o cuánto cuestan — "
        "nunca inventar precios.",
        args_model=NoArgs,
        handler=get_services,
    ),
    ToolDefinition(
        name="get_service_details",
        description="Detalle de un servicio puntual por nombre (precio, duración, descripción).",
        args_model=ServiceNameArgs,
        handler=get_service_details,
    ),
    ToolDefinition(
        name="get_professionals",
        description="Lista los profesionales del negocio, opcionalmente filtrados por servicio.",
        args_model=ProfessionalsArgs,
        handler=get_professionals,
    ),
    ToolDefinition(
        name="get_business_hours",
        description="Horario de atención semanal del negocio.",
        args_model=NoArgs,
        handler=get_business_hours,
    ),
]

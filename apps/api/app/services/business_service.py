import re
import unicodedata
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.business import Business
from app.models.membership import Membership, Role


def slugify(name: str) -> str:
    # Strip accents (á -> a) before dropping non-alphanumerics, since most
    # business names in the target market carry them (e.g. "Peluquería").
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")
    return slug or "negocio"


async def _unique_slug(db: AsyncSession, base_slug: str) -> str:
    slug = base_slug
    suffix = 1
    while await db.scalar(select(Business.id).where(Business.slug == slug)):
        suffix += 1
        slug = f"{base_slug}-{suffix}"
    return slug


async def create_business_for_user(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    name: str,
    timezone: str,
    locale: str,
    role: Role = Role.OWNER,
) -> Business:
    slug = await _unique_slug(db, slugify(name))
    business = Business(name=name, slug=slug, timezone=timezone, locale=locale)
    db.add(business)
    await db.flush()

    membership = Membership(user_id=user_id, business_id=business.id, role=role)
    db.add(membership)
    return business


async def list_businesses_for_user(db: AsyncSession, user_id: uuid.UUID) -> list[Membership]:
    result = await db.scalars(
        select(Membership)
        .where(Membership.user_id == user_id)
        .options(selectinload(Membership.business))
    )
    return list(result)

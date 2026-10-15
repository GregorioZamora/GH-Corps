from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.security import get_password_hash
from app.models.user import User
from app.models.review import Review

DEMO_REVIEWS = [
    (5, "¡Increíble calidad! El plano venía en varios formatos y es súper preciso.", "María G."),
    (4, "Muy buen trabajo, solo tardó un poco más de lo esperado en responder.", "Carlos R."),
    (5, "Justo lo que necesitaba para mi proyecto final. Lo recomiendo totalmente.", "Lucía P."),
    (3, "Buen diseño, aunque hubo que pedir un par de ajustes. Buen soporte.", "Andrés M."),
]


async def seed_admin(db: AsyncSession):
    """Create the default admin account if it does not exist."""
    result = await db.execute(select(User).where(User.role == "admin"))
    if result.scalars().first() is not None:
        return

    default_email = settings.COMPANY_EMAIL
    result = await db.execute(select(User).where(User.email == default_email))
    existing = result.scalar_one_or_none()

    if existing is not None:
        existing.role = "admin"
        existing.full_name = settings.COMPANY_NAME
        if not existing.hashed_password:
            existing.hashed_password = get_password_hash("admin1234")
        await db.commit()
        return

    admin = User(
        email=default_email,
        full_name="Administrador GH Diseños",
        hashed_password=get_password_hash("admin1234"),
        role="admin",
        auth_provider="local",
    )
    db.add(admin)
    await db.commit()


async def _seed_demo_reviews(db: AsyncSession):
    """Add sample global reviews when there are none yet."""
    count = await db.scalar(select(func.count()).select_from(Review)) or 0
    if count > 0:
        return

    for i, (rating, comment, name) in enumerate(DEMO_REVIEWS, start=1):
        email = f"review.demo{i}@test.local"
        result = await db.execute(select(User).where(User.email == email))
        reviewer = result.scalar_one_or_none()
        if reviewer is None:
            reviewer = User(
                email=email,
                full_name=name,
                hashed_password=get_password_hash("demo1234"),
                role="client",
                auth_provider="local",
            )
            db.add(reviewer)
            await db.flush()
        db.add(Review(user_id=reviewer.id, rating=rating, comment=comment))
    await db.commit()


async def seed_all(db: AsyncSession):
    await seed_admin(db)
    await _seed_demo_reviews(db)
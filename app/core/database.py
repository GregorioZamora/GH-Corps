from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def _column_exists(conn, table: str, column: str) -> bool:
    rows = (await conn.execute(text(f"PRAGMA table_info({table})"))).fetchall()
    return any(r[1] == column for r in rows)


async def _apply_light_migrations(conn) -> None:
    """Add columns introduced after the initial schema without dropping data."""
    table_names = {r[0] for r in (await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))).fetchall()}

    if "users" in table_names and not await _column_exists(conn, "users", "is_email_confirmed"):
        await conn.execute(text("ALTER TABLE users ADD COLUMN is_email_confirmed BOOLEAN DEFAULT 1"))

    if "commission_messages" in table_names and not await _column_exists(conn, "commission_messages", "is_read"):
        await conn.execute(text("ALTER TABLE commission_messages ADD COLUMN is_read BOOLEAN DEFAULT 0"))

    if "messages" in table_names and not await _column_exists(conn, "messages", "reply_to_id"):
        await conn.execute(text("ALTER TABLE messages ADD COLUMN reply_to_id INTEGER"))

    if "message_attachments" not in table_names and "messages" in table_names:
        await conn.execute(
            text(
                "CREATE TABLE message_attachments ("
                "id INTEGER PRIMARY KEY, "
                "message_id INTEGER NOT NULL REFERENCES messages(id), "
                "filename VARCHAR(255) NOT NULL, "
                "path VARCHAR(255) NOT NULL, "
                "created_at DATETIME)"
            )
        )


async def init_db():
    # Import all models so their tables are registered in Base.metadata.
    from app.models import user, product, order, message, commission, notification, review, cart_item  # noqa: F401
    from app.models.message_attachment import MessageAttachment  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _apply_light_migrations(conn)
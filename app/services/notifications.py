from sqlalchemy import select

from app.models.notification import Notification
from app.models.user import User


def notify_user(db, user_id: int, title: str, text: str = "", link: str = "") -> None:
    """Queue an in-app notification for a single user. The caller commits."""
    db.add(Notification(user_id=user_id, title=title, text=text or None, link=link or None))


async def notify_admins(db, title: str, text: str = "", link: str = "") -> None:
    """Queue an in-app notification for every admin. The caller commits."""
    ids = (await db.execute(select(User.id).where(User.role == "admin"))).scalars().all()
    for uid in ids:
        db.add(Notification(user_id=uid, title=title, text=text or None, link=link or None))
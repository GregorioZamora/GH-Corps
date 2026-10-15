from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, get_optional_user
from app.core.templating import get_templates
from app.models.notification import Notification
from app.services.i18n_helper import t

router = APIRouter(tags=["notifications"])
templates = get_templates()


@router.get("/notifications")
async def notifications_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(50)
    )
    items = result.scalars().all()
    unread = await db.scalar(
        select(func.count(Notification.id)).where(
            Notification.user_id == current_user.id, Notification.is_read == False
        )
    ) or 0

    return templates.TemplateResponse(
        "notifications.html",
        {
            "request": request,
            "lang": request.state.lang,
            "_t": lambda k, **kw: t(request, k, **kw),
            "current_user": current_user,
            "items": items,
            "unread": unread,
        },
    )


@router.post("/notifications/read-all")
async def mark_all_read(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    await db.execute(
        update(Notification)
        .where(Notification.user_id == current_user.id, Notification.is_read == False)
        .values(is_read=True)
    )
    await db.commit()
    return RedirectResponse(url="/notifications", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/notifications/{notification_id}/read")
async def mark_read(
    notification_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    notification = await db.get(Notification, notification_id)
    if notification is None or notification.user_id != current_user.id:
        return JSONResponse({"ok": False}, status_code=status.HTTP_404_NOT_FOUND)
    if not notification.is_read:
        notification.is_read = True
        await db.commit()
    return JSONResponse({"ok": True})


@router.get("/notifications/unread-count")
async def unread_count(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_optional_user),
):
    if current_user is None:
        return JSONResponse({"count": 0})

    count = await db.scalar(
        select(func.count(Notification.id)).where(
            Notification.user_id == current_user.id, Notification.is_read == False
        )
    ) or 0
    return JSONResponse({"count": count})
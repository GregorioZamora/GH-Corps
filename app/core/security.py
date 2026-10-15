from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.database import get_db

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None


def _login_redirect_exc(cause: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_303_SEE_OTHER,
        headers={"Location": "/auth/login"},
        detail=cause,
    )


async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)):
    from app.models.user import User

    token = request.cookies.get("access_token")
    if not token:
        raise _login_redirect_exc("No token")

    payload = decode_token(token)
    if payload is None or payload.get("sub") is None:
        raise _login_redirect_exc("Invalid token")

    user = await db.get(User, int(payload["sub"]))
    if user is None:
        raise _login_redirect_exc("User not found")
    if not user.is_active:
        raise _login_redirect_exc("Inactive user")

    return user


async def get_optional_user(request: Request, db: AsyncSession = Depends(get_db)):
    from app.models.user import User

    token = request.cookies.get("access_token")
    if not token:
        return None

    payload = decode_token(token)
    if payload is None or payload.get("sub") is None:
        return None

    user = await db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        return None
    return user


def require_role(role: str):
    async def role_checker(request: Request, db: AsyncSession = Depends(get_db)):
        from app.models.user import User

        token = request.cookies.get("access_token")
        if not token:
            raise _login_redirect_exc("Login required")

        payload = decode_token(token)
        if payload is None or payload.get("sub") is None:
            raise _login_redirect_exc("Invalid token")

        user = await db.get(User, int(payload["sub"]))
        if user is None or not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        if user.role != role:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

        return user

    return role_checker
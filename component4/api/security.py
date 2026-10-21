"""Password hashing, JWT tokens and role-based access control (SO4, FR6, FR7)."""

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_db
from models import User
from settings import JWT_ALGORITHM, JWT_EXPIRE_MINUTES, JWT_SECRET

bearer = HTTPBearer(auto_error=False)


def hash_password(password):
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password, password_hash):
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_token(user):
    """Signed JWT carrying who the user is, their role and clinic."""
    now = datetime.now(timezone.utc)
    claims = {
        "sub": user.username,
        "role": user.role,
        "clinic_id": user.clinic_id,
        "iat": now,
        "exp": now + timedelta(minutes=JWT_EXPIRE_MINUTES),
    }
    return jwt.encode(claims, JWT_SECRET, algorithm=JWT_ALGORITHM)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
):
    """Dependency: reject the request (401) unless it has a valid, unexpired JWT."""
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    try:
        claims = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:  # bad signature, expired, malformed...
        raise unauthorized
    user = db.scalars(select(User).where(User.username == claims.get("sub"))).first()
    if user is None:
        raise unauthorized
    return user


def require_roles(*roles):
    """Dependency factory: allow only users whose role is in `roles` (else 403)."""
    def checker(user: User = Depends(get_current_user)):
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return user
    return checker

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from audit import write_audit
from database import get_db
from models import User
from schemas import LoginRequest, LoginResponse, UserOut
from security import create_token, get_current_user, verify_password

router = APIRouter(prefix="/api/v1/c4/auth", tags=["Authentication"])


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalars(select(User).where(User.username == body.username)).first()
    if user is None or not verify_password(body.password, user.password_hash):
        # Failed attempts are audited too; the same message is returned
        # whether the username or the password was wrong.
        write_audit(db, actor=body.username, role="unknown", action="auth.login_failed")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

    write_audit(db, actor=user.username, role=user.role, clinic_id=user.clinic_id, action="auth.login")
    return LoginResponse(
        access_token=create_token(user),
        user=UserOut(username=user.username, role=user.role, clinic_id=user.clinic_id),
    )


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return UserOut(username=user.username, role=user.role, clinic_id=user.clinic_id)

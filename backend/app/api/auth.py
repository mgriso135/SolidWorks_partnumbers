from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import get_current_user
from ..models import User
from ..schemas import LoginRequest, TokenOut, UserOut
from ..security import create_access_token, verify_password
from ..services import audit

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> TokenOut:
    email = payload.email.strip().lower()
    user = db.scalar(
        select(User)
        .where(func.lower(User.email) == email, User.active.is_(True))
        .order_by(User.created_at)
    )
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token = create_access_token(user_id=user.id, tenant_id=user.tenant_id, role=user.role)
    audit.record(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="auth.login",
        entity_type="user",
        entity_id=user.id,
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return TokenOut(access_token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(user)

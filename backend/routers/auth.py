"""
Auth Router — Owner: M2 (F01-F04)
Exposes /auth/register, /auth/login, /auth/me, /auth/preferences.

STATUS:
- /auth/register (F01): IMPLEMENTED (Task 7)
- /auth/login (F02): IMPLEMENTED (Task 7)
- /auth/me (F03): NOT YET IMPLEMENTED (Task 8)
- /auth/preferences (F04): NOT YET IMPLEMENTED (Task 8)
"""
import os
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from jose import jwt

from backend.models_temp import get_db, User

router = APIRouter(prefix="/auth", tags=["Auth"])

# bcrypt, cost factor 12 per PRD F01 spec. Loaded once, not per-request.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"


class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: str
    name: str
    email: str

    class Config:
        from_attributes = True


class AuthResponse(BaseModel):
    token: str
    user: UserOut


def create_access_token(user_id: str) -> str:
    """JWT payload: { sub: user_id, exp: now + 24h }, per Build Guide 4.2."""
    payload = {
        "sub": user_id,
        "exp": datetime.utcnow() + timedelta(hours=24),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


@router.post("/register", response_model=AuthResponse)
async def register(req: RegisterRequest, db: Session = Depends(get_db)):
    """
    F01: Create a new user account.
    - Duplicate email -> 409 (per AC-01)
    - Password hashed with bcrypt, cost 12
    - Returns a JWT on success, same as login
    """
    existing = db.query(User).filter(User.email == req.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered.")

    hashed_password = pwd_context.hash(req.password)
    new_user = User(
        name=req.name,
        email=req.email,
        password_hash=hashed_password,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    token = create_access_token(new_user.id)
    return {"token": token, "user": new_user}


@router.post("/login", response_model=AuthResponse)
async def login(req: LoginRequest, db: Session = Depends(get_db)):
    """
    F02: Authenticate an existing user.
    - Invalid email or password -> 401 (per AC-02)
    - Returns a JWT valid for 24h on success
    """
    user = db.query(User).filter(User.email == req.email).first()

    if not user or not pwd_context.verify(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    token = create_access_token(user.id)
    return {"token": token, "user": user}
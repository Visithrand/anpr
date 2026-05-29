"""
backend/routes/auth.py
~~~~~~~~~~~~~~~~~~~~~~
Admin authentication endpoints:
  POST /auth/login     → validate credentials, return JWT
  POST /auth/register  → create new admin (requires valid token)
  GET  /auth/me        → return current admin info
"""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from jose import JWTError, jwt

from backend.utils.database import get_db
from backend.models.models import Admin

router = APIRouter(prefix="/auth", tags=["auth"])

# --- Config (from centralized settings) ---
from backend.config import settings

SECRET_KEY = settings.JWT_SECRET_KEY
ALGORITHM = settings.JWT_ALGORITHM
ACCESS_TOKEN_EXPIRE_HOURS = settings.JWT_EXPIRE_HOURS

pwd_context = CryptContext(schemes=["bcrypt_sha256"], deprecated="auto")
security = HTTPBearer(auto_error=False)


# --- Pydantic Schemas ---
class LoginRequest(BaseModel):
    email: str
    password: str

class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str = "Admin"

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    name: str
    email: str
    role: str


# --- Helpers ---
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_admin(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> Admin:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    admin = db.query(Admin).filter(Admin.email == email).first()
    if admin is None:
        raise HTTPException(status_code=401, detail="Admin not found")
    return admin


def seed_default_admin(db: Session):
    """Create default admin if none exists."""
    existing = db.query(Admin).first()
    if not existing:
        admin = Admin(
            email="admin@anpr.os",
            password_hash=pwd_context.hash("admin123"),
            name="System Administrator",
            role="superadmin",
        )
        db.add(admin)
        db.commit()


# --- Routes ---
@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    admin = db.query(Admin).filter(Admin.email == req.email).first()
    if not admin or not pwd_context.verify(req.password, admin.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    token = create_access_token(data={"sub": admin.email})
    return TokenResponse(
        access_token=token,
        name=admin.name,
        email=admin.email,
        role=admin.role,
    )


@router.post("/register")
def register_admin(
    req: RegisterRequest,
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    # Only existing admins can register new admins
    existing = db.query(Admin).filter(Admin.email == req.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    admin = Admin(
        email=req.email,
        password_hash=pwd_context.hash(req.password),
        name=req.name,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return {"message": "Admin registered successfully", "email": admin.email, "name": admin.name}


@router.get("/me")
def get_me(current_admin: Admin = Depends(get_current_admin)):
    return {
        "id": current_admin.id,
        "email": current_admin.email,
        "name": current_admin.name,
        "role": current_admin.role,
        "created_at": current_admin.created_at,
    }

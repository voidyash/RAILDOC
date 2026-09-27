import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from dotenv import load_dotenv

# Load .env BEFORE reading JWT_SECRET_KEY — this module is imported before
# app.db.queries (which also calls load_dotenv), so without this the secret
# fell back to a random value on every process start, invalidating all
# previously issued tokens whenever the backend restarted.
load_dotenv()

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

SECRET_KEY = os.getenv("JWT_SECRET_KEY", secrets.token_urlsafe(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

pwd_context = CryptContext(schemes=["sha256_crypt"], deprecated="auto")
security = HTTPBearer(auto_error=False)


class UserRole(str):
    ADMIN = "admin"
    PLANNER = "planner"
    OPERATIONS = "operations"
    ENGINEER = "engineer"


class TokenData(BaseModel):
    username: Optional[str] = None
    roles: list[str] = []


class User(BaseModel):
    username: str
    hashed_password: str
    roles: list[str]
    is_active: bool = True
    created_at: datetime = datetime.now()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> TokenData:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "access":
            raise JWTError("Invalid token type")
        username: str = payload.get("sub")
        roles: list[str] = payload.get("roles", [])
        if username is None:
            raise JWTError("Invalid token")
        return TokenData(username=username, roles=roles)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> TokenData:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return decode_token(credentials.credentials)


def require_roles(*allowed_roles: str):
    def role_checker(current_user: TokenData = Depends(get_current_user)) -> TokenData:
        if not any(role in current_user.roles for role in allowed_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user
    return role_checker


def get_admin_user(current_user: TokenData = Depends(require_roles(UserRole.ADMIN))) -> TokenData:
    return current_user


def get_planner_user(current_user: TokenData = Depends(require_roles(UserRole.ADMIN, UserRole.PLANNER))) -> TokenData:
    return current_user


def get_operations_user(current_user: TokenData = Depends(require_roles(UserRole.ADMIN, UserRole.OPERATIONS))) -> TokenData:
    return current_user


def get_engineer_user(current_user: TokenData = Depends(require_roles(UserRole.ADMIN, UserRole.ENGINEER))) -> TokenData:
    return current_user


def get_authenticated_user(current_user: TokenData = Depends(get_current_user)) -> TokenData:
    return current_user
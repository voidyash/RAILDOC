import threading
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from app.core.security import (
    User, get_password_hash, verify_password,
    create_access_token, create_refresh_token,
    get_current_user, get_admin_user, TokenData
)
from app.core.audit import log_audit, AuditEventType

router = APIRouter(prefix="/api/auth", tags=["authentication"])


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=100)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: str


class UserCreateRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, pattern="^[a-zA-Z0-9_-]+$")
    password: str = Field(..., min_length=8, max_length=100)
    roles: list[str] = Field(default_factory=list)


class UserResponse(BaseModel):
    username: str
    roles: list[str]
    is_active: bool
    created_at: str


MOCK_USERS: dict[str, User] = {}
_MOCK_USERS_LOCK = threading.Lock()


def init_mock_users():
    # Hashing four demo passwords costs ~0.5s of CPU; guard the
    # check-then-init, and call this via run_in_threadpool from handlers.
    with _MOCK_USERS_LOCK:
        if not MOCK_USERS:
            _populate_mock_users()


def _populate_mock_users():
    if not MOCK_USERS:
        MOCK_USERS["admin"] = User(
            username="admin",
            hashed_password=get_password_hash("admin123"),
            roles=["admin", "planner", "operations", "engineer"],
        )
        MOCK_USERS["planner"] = User(
            username="planner",
            hashed_password=get_password_hash("planner123"),
            roles=["planner"],
        )
        MOCK_USERS["operations"] = User(
            username="operations",
            hashed_password=get_password_hash("operations123"),
            roles=["operations"],
        )
        MOCK_USERS["engineer"] = User(
            username="engineer",
            hashed_password=get_password_hash("engineer123"),
            roles=["engineer"],
        )


def get_client_ip(request: Request) -> str:
    client_ip = request.client.host if request.client else "unknown"
    if request.headers.get("x-forwarded-for"):
        client_ip = request.headers["x-forwarded-for"].split(",")[0].strip()
    return client_ip


@router.post("/login", response_model=TokenResponse)
async def login(request: Request, credentials: LoginRequest):
    await run_in_threadpool(init_mock_users)
    client_ip = get_client_ip(request)

    user = MOCK_USERS.get(credentials.username)
    # sha256 verification is CPU-bound (~100ms): keep it off the event loop
    # so a burst of logins cannot stall every other request.
    password_ok = user is not None and await run_in_threadpool(
        verify_password, credentials.password, user.hashed_password
    )
    if not password_ok:
        log_audit(
            AuditEventType.USER_LOGIN,
            username=credentials.username,
            client_ip=client_ip,
            status="failure",
            error_message="Invalid credentials"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    if not user.is_active:
        log_audit(
            AuditEventType.USER_LOGIN,
            username=credentials.username,
            client_ip=client_ip,
            status="failure",
            error_message="Account disabled"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    access_token = create_access_token(
        data={"sub": user.username, "roles": user.roles},
        expires_delta=timedelta(minutes=30)
    )
    refresh_token = create_refresh_token(data={"sub": user.username, "roles": user.roles})

    log_audit(
        AuditEventType.USER_LOGIN,
        username=user.username,
        client_ip=client_ip,
        status="success"
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=30 * 60
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: Request, token_request: RefreshRequest):
    client_ip = get_client_ip(request)
    try:
        from jose import jwt
        from app.core.security import SECRET_KEY, ALGORITHM
        payload = jwt.decode(token_request.refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")

        username = payload.get("sub")
        roles = payload.get("roles", [])

        access_token = create_access_token(data={"sub": username, "roles": roles})
        new_refresh_token = create_refresh_token(data={"sub": username, "roles": roles})

        log_audit(
            AuditEventType.USER_LOGOUT,
            username=username,
            client_ip=client_ip,
            status="success"
        )

        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
            expires_in=30 * 60
        )
    except Exception as e:
        log_audit(
            AuditEventType.USER_LOGOUT,
            username="unknown",
            client_ip=client_ip,
            status="failure",
            error_message=str(e)
        )
        raise HTTPException(status_code=401, detail="Invalid refresh token")


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: TokenData = Depends(get_current_user)):
    await run_in_threadpool(init_mock_users)
    user = MOCK_USERS.get(current_user.username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse(
        username=user.username,
        roles=user.roles,
        is_active=user.is_active,
        created_at=user.created_at.isoformat()
    )


@router.post("/users", response_model=UserResponse)
async def create_user(
    request: Request,
    user_data: UserCreateRequest,
    current_user: TokenData = Depends(get_admin_user)
):
    await run_in_threadpool(init_mock_users)
    client_ip = get_client_ip(request)

    if user_data.username in MOCK_USERS:
        raise HTTPException(status_code=400, detail="Username already exists")

    valid_roles = {"admin", "planner", "operations", "engineer"}
    invalid_roles = set(user_data.roles) - valid_roles
    if invalid_roles:
        raise HTTPException(status_code=400, detail=f"Invalid roles: {invalid_roles}")

    # Auto-assign viewer role with limited permissions to all new users
    final_roles = list(user_data.roles) + ["viewer"]

    # Password hashing is deliberately slow: run it on a worker thread.
    hashed = await run_in_threadpool(get_password_hash, user_data.password)
    if user_data.username in MOCK_USERS:
        # Re-check: we awaited above, so another request may have won.
        raise HTTPException(status_code=400, detail="Username already exists")

    user = User(
        username=user_data.username,
        hashed_password=hashed,
        roles=final_roles,
    )
    MOCK_USERS[user_data.username] = user

    log_audit(
        AuditEventType.CONFIG_CHANGED,
        username=current_user.username,
        client_ip=client_ip,
        resource_type="user",
        resource_id=user_data.username,
        action="create",
        details={"roles": final_roles}
    )

    return UserResponse(
        username=user.username,
        roles=user.roles,
        is_active=user.is_active,
        created_at=user.created_at.isoformat()
    )


@router.get("/users", response_model=list[UserResponse])
async def list_users(current_user: TokenData = Depends(get_admin_user)):
    await run_in_threadpool(init_mock_users)
    return [
        UserResponse(
            username=user.username,
            roles=user.roles,
            is_active=user.is_active,
            created_at=user.created_at.isoformat()
        )
        for user in MOCK_USERS.values()
    ]
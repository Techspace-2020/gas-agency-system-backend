from sqlalchemy.orm import Session
from sqlalchemy import text
import logging
from app.models.schema import(UserCreate, LoginRequest, TokenResponse)
from app.core.security import pwd_context, create_access_token, create_refresh_token
from app.core.exceptions import BusinessException

logger = logging.getLogger(__name__)


def _get_user_by_username(db: Session, username: str):
    return db.execute(
        text("SELECT user_id, username, password_hash, role, is_active, created_at FROM users WHERE username = :username"),
        {"username": username}
    ).fetchone()


def register_admin_service(data: UserCreate, db: Session):
    existing = _get_user_by_username(db, data.username)
    if existing:
        raise BusinessException("Username already exists", 409)

    password_hash = pwd_context.hash(data.password)
    role = "ADMIN"

    db.execute(
        text("INSERT INTO users (username, password_hash, role, is_active) VALUES (:username, :password_hash, :role, :is_active)"),
        {
            "username": data.username,
            "password_hash": password_hash,
            "role": role,
            "is_active": 1,
        },
    )
    db.commit()

    user = _get_user_by_username(db, data.username)
    return {
        "success": True,
        "message": "Admin user created",
        "data": dict(user._mapping) if user else None,
    }


def register_employee_service(data: UserCreate, db: Session):
    existing = _get_user_by_username(db, data.username)
    if existing:
        raise BusinessException("Username already exists", 409)

    password_hash = pwd_context.hash(data.password)
    # Use provided role if given, otherwise default to OPERATOR
    role = data.role.value if hasattr(data.role, "value") else str(data.role)

    db.execute(
        text("INSERT INTO users (username, password_hash, role, is_active) VALUES (:username, :password_hash, :role, :is_active)"),
        {
            "username": data.username,
            "password_hash": password_hash,
            "role": role,
            "is_active": 1,
        },
    )
    db.commit()

    user = _get_user_by_username(db, data.username)
    return {
        "success": True,
        "message": "Employee user created",
        "data": dict(user._mapping) if user else None,
    }


def _generate_tokens_for_user(user_row) -> dict:
    payload = {"sub": user_row["user_id"], "username": user_row["username"], "role": user_row["role"]}
    access = create_access_token(payload)
    refresh = create_refresh_token(payload)
    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
        "user_info": {"user_id": user_row["user_id"], "username": user_row["username"], "role": user_row["role"]},
    }


def employee_login_service(data: LoginRequest, db: Session):
    user = db.execute(
        text("SELECT user_id, username, password_hash, role FROM users WHERE username = :username AND is_active = 1"),
        {"username": data.username},
    ).fetchone()

    if not user:
        raise BusinessException("Invalid credentials", 401)

    password_hash = user["password_hash"]
    if not pwd_context.verify(data.password, password_hash):
        raise BusinessException("Invalid credentials", 401)

    return _generate_tokens_for_user(user._mapping)


def admin_login_service(data:LoginRequest, db: Session):
    user = db.execute(
        text("SELECT user_id, username, password_hash, role FROM users WHERE username = :username AND is_active = 1"),
        {"username": data.username},
    ).fetchone()

    if not user:
        raise BusinessException("Invalid credentials", 401)

    password_hash = user["password_hash"]
    if not pwd_context.verify(data.password, password_hash):
        raise BusinessException("Invalid credentials", 401)

    # ensure role is ADMIN
    if user["role"] != "ADMIN":
        raise BusinessException("Not an admin user", 403)

    return _generate_tokens_for_user(user._mapping)

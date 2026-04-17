from __future__ import annotations

import hmac
import json
import urllib.request
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Annotated, Literal

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel, Field, StringConstraints, ValidationError, field_validator
from sqlalchemy.orm import Session

from .auth_utils import hash_api_key, month_window_start, utc_now, verify_password
from .config import settings
from .db import ApiKey, CollectionPermission, SessionLocal, UserAccount

UserName = Annotated[str, StringConstraints(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_.-]+$")]
CollectionName = Annotated[
    str,
    StringConstraints(min_length=1, max_length=100, pattern=r"^(\*|[A-Za-z0-9][A-Za-z0-9._-]+)$"),
]


class AuthUserConfig(BaseModel):
    username: UserName
    password: Annotated[str, StringConstraints(min_length=8, max_length=128)]
    role: Literal["admin", "editor", "viewer"]
    collections: list[CollectionName] = Field(default_factory=list, max_length=50)

    @field_validator("collections")
    @classmethod
    def validate_collections(cls, values: list[str], info):
        role = info.data.get("role")
        if role in {"viewer", "editor"} and not values:
            raise ValueError("Non-admin users must declare at least one allowed collection")
        return values


class CurrentUser(BaseModel):
    username: UserName
    role: Literal["admin", "editor", "viewer"]
    collections: set[str] = Field(default_factory=set)
    collection_permissions: dict[str, Literal["read", "write"]] = Field(default_factory=dict)
    auth_provider: Literal["local", "oidc", "api_key"] = "local"
    api_key_id: int | None = None

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/v1/auth/token", auto_error=False)


def _auth_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@lru_cache
def _user_store() -> dict[str, AuthUserConfig]:
    try:
        raw = json.loads(settings.auth_users_json)
    except json.JSONDecodeError as exc:
        raise RuntimeError("AUTH_USERS_JSON must be valid JSON") from exc

    if not isinstance(raw, list):
        raise RuntimeError("AUTH_USERS_JSON must be a JSON array")

    users: dict[str, AuthUserConfig] = {}
    for item in raw:
        try:
            user = AuthUserConfig.model_validate(item)
        except ValidationError as exc:
            raise RuntimeError(f"Invalid AUTH_USERS_JSON entry: {exc}") from exc
        if user.username in users:
            raise RuntimeError(f"Duplicate username in AUTH_USERS_JSON: {user.username}")
        users[user.username] = user

    if not users:
        raise RuntimeError("AUTH_USERS_JSON must define at least one user")

    return users


def _permissions_from_collections(role: str, collections: list[str]) -> dict[str, Literal["read", "write"]]:
    if role == "admin":
        return {"*": "write"}
    return {c: "write" if role == "editor" else "read" for c in collections if c}


def _permissions_to_collection_set(permissions: dict[str, str]) -> set[str]:
    return {name for name, mode in permissions.items() if mode in {"read", "write"}}


def _db_permissions_for_user(db: Session, username: str, role: str, fallback_collections: list[str] | None = None) -> dict[str, Literal["read", "write"]]:
    if role == "admin":
        return {"*": "write"}

    rows = db.query(CollectionPermission).filter(CollectionPermission.username == username).all()
    permissions: dict[str, Literal["read", "write"]] = {}
    for row in rows:
        if row.can_write:
            permissions[row.collection] = "write"
        elif row.can_read:
            permissions[row.collection] = "read"

    if permissions:
        return permissions
    if fallback_collections:
        return _permissions_from_collections(role, fallback_collections)
    return {}


def authenticate_user(username: str, password: str, db: Session | None = None) -> CurrentUser | None:
    if db is not None and settings.db_auth_enabled:
        db_user = db.query(UserAccount).filter(UserAccount.username == username, UserAccount.is_active.is_(True)).first()
        if db_user and db_user.password_hash and verify_password(password, db_user.password_hash):
            perms = _db_permissions_for_user(db, username=db_user.username, role=db_user.role)
            db_user.last_login_at = utc_now()
            return CurrentUser(
                username=db_user.username,
                role=db_user.role,
                collection_permissions=perms,
                collections=_permissions_to_collection_set(perms),
                auth_provider="local",
            )

    user = _user_store().get(username)
    if not user:
        return None
    if not hmac.compare_digest(user.password, password):
        return None

    perms = _permissions_from_collections(user.role, user.collections)
    return CurrentUser(
        username=user.username,
        role=user.role,
        collection_permissions=perms,
        collections=_permissions_to_collection_set(perms),
        auth_provider="local",
    )


def create_access_token(user: CurrentUser | AuthUserConfig) -> tuple[str, int]:
    if isinstance(user, AuthUserConfig):
        perms = _permissions_from_collections(user.role, user.collections)
        principal = CurrentUser(
            username=user.username,
            role=user.role,
            collections=_permissions_to_collection_set(perms),
            collection_permissions=perms,
            auth_provider="local",
        )
    else:
        principal = user

    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": principal.username,
        "role": principal.role,
        "collections": sorted(principal.collections),
        "permissions": principal.collection_permissions,
        "provider": principal.auth_provider,
        "iat": int(now.timestamp()),
        "exp": int(expires.timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, int((expires - now).total_seconds())


def _build_current_user_from_payload(payload: dict, *, default_provider: str = "local") -> CurrentUser:
    username = payload.get("sub")
    role = payload.get("role")
    collections = payload.get("collections", [])
    permissions = payload.get("permissions") or {}

    if not isinstance(username, str) or role not in {"admin", "editor", "viewer"}:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not isinstance(collections, list):
        collections = []

    parsed_permissions: dict[str, Literal["read", "write"]] = {}
    if isinstance(permissions, dict):
        for key, value in permissions.items():
            if isinstance(key, str) and value in {"read", "write"}:
                parsed_permissions[key] = value
    if not parsed_permissions:
        parsed_permissions = _permissions_from_collections(role, [c for c in collections if isinstance(c, str)])

    allowed = _permissions_to_collection_set(parsed_permissions)
    if role == "admin":
        allowed.add("*")

    provider = payload.get("provider")
    if provider not in {"local", "oidc", "api_key"}:
        provider = default_provider

    return CurrentUser(
        username=username,
        role=role,
        collections=allowed,
        collection_permissions=parsed_permissions,
        auth_provider=provider,
    )


def _try_jwt_secret(token: str) -> CurrentUser | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None
    return _build_current_user_from_payload(payload, default_provider="local")


@lru_cache(maxsize=2)
def _fetch_jwks(jwks_url: str) -> dict:
    with urllib.request.urlopen(jwks_url, timeout=5) as response:
        data = response.read().decode("utf-8")
    return json.loads(data)


def _try_oidc_token(token: str, db: Session | None = None) -> CurrentUser | None:
    if not settings.oidc_issuer_url:
        return None

    jwks_url = settings.oidc_jwks_url or f"{settings.oidc_issuer_url.rstrip('/')}/protocol/openid-connect/certs"

    try:
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        jwks = _fetch_jwks(jwks_url)
        keys = jwks.get("keys", []) if isinstance(jwks, dict) else []
        key = next((item for item in keys if isinstance(item, dict) and item.get("kid") == kid), None)
        if not key and keys:
            key = keys[0]
        if not key:
            return None

        options = {"verify_aud": bool(settings.oidc_audience)}
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256", "RS384", "RS512"],
            audience=settings.oidc_audience or None,
            issuer=settings.oidc_issuer_url,
            options=options,
        )
    except (JWTError, ValueError, KeyError, TimeoutError, OSError):
        return None

    username_claim = claims.get(settings.oidc_claim_username)
    if not isinstance(username_claim, str):
        username_claim = claims.get("preferred_username") or claims.get("email") or claims.get("sub")
    if not isinstance(username_claim, str):
        return None

    role_claim = claims.get(settings.oidc_claim_role, "viewer")
    role = role_claim if role_claim in {"admin", "editor", "viewer"} else "viewer"

    collections_claim = claims.get(settings.oidc_claim_collections, [])
    collections: list[str] = []
    if isinstance(collections_claim, str):
        collections = [collections_claim]
    elif isinstance(collections_claim, list):
        collections = [c for c in collections_claim if isinstance(c, str)]

    permissions = _permissions_from_collections(role, collections)

    if db is not None and settings.db_auth_enabled:
        db_user = db.query(UserAccount).filter(UserAccount.username == username_claim).first()
        if not db_user:
            db_user = UserAccount(
                username=username_claim,
                password_hash=None,
                role=role,
                auth_provider="oidc",
                external_subject=str(claims.get("sub") or ""),
                monthly_quota=settings.default_user_quota_per_month,
                quota_reset_at=month_window_start(),
            )
            db.add(db_user)
        else:
            db_user.role = role
            db_user.auth_provider = "oidc"
            db_user.external_subject = str(claims.get("sub") or db_user.external_subject or "")
            db_user.is_active = True

        existing_permission = (
            db.query(CollectionPermission).filter(CollectionPermission.username == username_claim).first()
        )
        if not existing_permission:
            for collection, mode in permissions.items():
                if collection == "*":
                    continue
                db.add(
                    CollectionPermission(
                        username=username_claim,
                        collection=collection,
                        can_read=True,
                        can_write=mode == "write",
                    )
                )

        db_permissions = _db_permissions_for_user(db, username_claim, role, fallback_collections=collections)
        permissions = db_permissions or permissions

    return CurrentUser(
        username=username_claim,
        role=role,
        collection_permissions=permissions,
        collections=_permissions_to_collection_set(permissions),
        auth_provider="oidc",
    )


def _reset_quota_if_needed(obj) -> None:
    month_start = month_window_start()
    quota_reset_at = getattr(obj, "quota_reset_at", None)
    if quota_reset_at is None or quota_reset_at < month_start:
        obj.used_this_month = 0
        obj.quota_reset_at = month_start


def _authenticate_api_key(raw_key: str, db: Session) -> CurrentUser | None:
    key_hash = hash_api_key(raw_key)
    key_row = (
        db.query(ApiKey)
        .filter(
            ApiKey.key_hash == key_hash,
            ApiKey.is_active.is_(True),
        )
        .first()
    )
    if not key_row:
        return None

    if key_row.expires_at and key_row.expires_at < utc_now():
        return None

    owner = (
        db.query(UserAccount)
        .filter(UserAccount.username == key_row.owner_username, UserAccount.is_active.is_(True))
        .first()
    )
    if not owner:
        return None

    _reset_quota_if_needed(key_row)
    _reset_quota_if_needed(owner)

    if key_row.used_this_month >= key_row.monthly_quota:
        raise HTTPException(status_code=429, detail="API key monthly quota exceeded")
    if owner.used_this_month >= owner.monthly_quota:
        raise HTTPException(status_code=429, detail="User monthly quota exceeded")

    key_row.used_this_month += 1
    key_row.last_used_at = utc_now()
    owner.used_this_month += 1

    permissions = _db_permissions_for_user(db, owner.username, owner.role)
    current = CurrentUser(
        username=owner.username,
        role=owner.role,
        collection_permissions=permissions,
        collections=_permissions_to_collection_set(permissions),
        auth_provider="api_key",
        api_key_id=key_row.id,
    )
    return current


def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
    db: Session = Depends(_auth_db),
) -> CurrentUser:
    if not settings.auth_required:
        return CurrentUser(
            username="local-dev",
            role="admin",
            collection_permissions={"*": "write"},
            collections={"*"},
            auth_provider="local",
        )

    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    raw_api_key = x_api_key
    if not raw_api_key and token and token.startswith(settings.api_key_prefix):
        raw_api_key = token

    if raw_api_key:
        user = _authenticate_api_key(raw_api_key, db)
        if user:
            db.commit()
            return user
        raise unauthorized

    if not token:
        raise unauthorized

    user = _try_jwt_secret(token)
    if user:
        return user

    user = _try_oidc_token(token, db if settings.db_auth_enabled else None)
    if user:
        if settings.db_auth_enabled:
            db.commit()
        return user

    raise unauthorized


def require_admin(current_user: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return current_user


def ensure_collection_access(current_user: CurrentUser, collection: str, write: bool = False) -> None:
    if current_user.is_admin:
        return

    wildcard_mode = current_user.collection_permissions.get("*")
    if wildcard_mode == "write" or (wildcard_mode == "read" and not write):
        return

    collection_mode = current_user.collection_permissions.get(collection)
    if write:
        if collection_mode != "write":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Write access denied for collection '{collection}'",
            )
        return

    if collection_mode not in {"read", "write"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Access denied for collection '{collection}'")

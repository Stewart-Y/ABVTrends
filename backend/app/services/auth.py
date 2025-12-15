"""
ABVTrends - Authentication Service

Business logic for password hashing, JWT token management, and API key generation.
"""

import secrets
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import ApiKey, User, UserRole

# Password hashing context using bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# =============================================================================
# Password Functions
# =============================================================================


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.

    Args:
        password: Plain text password

    Returns:
        Hashed password string
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.

    Args:
        plain_password: Plain text password to verify
        hashed_password: Stored password hash

    Returns:
        True if password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


# =============================================================================
# JWT Token Functions
# =============================================================================


def create_access_token(user_id: UUID, role: UserRole) -> tuple[str, int]:
    """
    Create a JWT access token.

    Args:
        user_id: User's UUID
        role: User's role

    Returns:
        Tuple of (token_string, expires_in_seconds)
    """
    expires_delta = timedelta(hours=settings.jwt_expire_hours)
    expire = datetime.utcnow() + expires_delta

    payload = {
        "sub": str(user_id),
        "role": role.value,
        "exp": expire,
        "iat": datetime.utcnow(),
    }

    token = jwt.encode(
        payload,
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )

    expires_in = int(expires_delta.total_seconds())

    return token, expires_in


def decode_token(token: str) -> Optional[dict]:
    """
    Decode and validate a JWT token.

    Args:
        token: JWT token string

    Returns:
        Decoded payload dict or None if invalid
    """
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except JWTError:
        return None


# =============================================================================
# API Key Functions
# =============================================================================


def generate_api_key() -> tuple[str, str]:
    """
    Generate a new API key.

    Returns:
        Tuple of (plain_key, hashed_key)
        The plain_key should be shown to user once, hashed_key is stored.
    """
    # Generate a secure random key (43 chars base64)
    plain_key = f"abv_{secrets.token_urlsafe(32)}"
    hashed_key = pwd_context.hash(plain_key)
    return plain_key, hashed_key


def verify_api_key(plain_key: str, hashed_key: str) -> bool:
    """
    Verify an API key against its hash.

    Args:
        plain_key: Plain API key from request header
        hashed_key: Stored hash

    Returns:
        True if key matches, False otherwise
    """
    return pwd_context.verify(plain_key, hashed_key)


# =============================================================================
# Database Operations
# =============================================================================


async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    """
    Get a user by email address.

    Args:
        db: Database session
        email: User's email

    Returns:
        User if found, None otherwise
    """
    result = await db.execute(
        select(User).where(User.email == email)
    )
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: UUID) -> Optional[User]:
    """
    Get a user by ID.

    Args:
        db: Database session
        user_id: User's UUID

    Returns:
        User if found, None otherwise
    """
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    return result.scalar_one_or_none()


async def create_user(
    db: AsyncSession,
    email: str,
    password: str,
    role: UserRole = UserRole.USER,
) -> User:
    """
    Create a new user.

    Args:
        db: Database session
        email: User's email
        password: Plain text password (will be hashed)
        role: User's role (default: USER)

    Returns:
        Created User instance
    """
    user = User(
        email=email,
        hashed_password=hash_password(password),
        role=role,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


async def authenticate_user(
    db: AsyncSession,
    email: str,
    password: str,
) -> Optional[User]:
    """
    Authenticate a user by email and password.

    Args:
        db: Database session
        email: User's email
        password: Plain text password

    Returns:
        User if credentials valid, None otherwise
    """
    user = await get_user_by_email(db, email)
    if not user:
        return None
    if not user.is_active:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


async def get_api_key_by_id(
    db: AsyncSession,
    key_id: UUID,
    user_id: UUID,
) -> Optional[ApiKey]:
    """
    Get an API key by ID, scoped to a specific user.

    Args:
        db: Database session
        key_id: API key UUID
        user_id: Owner's UUID

    Returns:
        ApiKey if found and owned by user, None otherwise
    """
    result = await db.execute(
        select(ApiKey).where(
            ApiKey.id == key_id,
            ApiKey.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def get_user_api_keys(db: AsyncSession, user_id: UUID) -> list[ApiKey]:
    """
    Get all API keys for a user.

    Args:
        db: Database session
        user_id: User's UUID

    Returns:
        List of ApiKey instances
    """
    result = await db.execute(
        select(ApiKey)
        .where(ApiKey.user_id == user_id)
        .order_by(ApiKey.created_at.desc())
    )
    return list(result.scalars().all())


async def create_api_key(
    db: AsyncSession,
    user_id: UUID,
    name: str,
) -> tuple[ApiKey, str]:
    """
    Create a new API key for a user.

    Args:
        db: Database session
        user_id: Owner's UUID
        name: Friendly name for the key

    Returns:
        Tuple of (ApiKey instance, plain_key)
        The plain_key is only available here - store it securely!
    """
    plain_key, hashed_key = generate_api_key()

    api_key = ApiKey(
        user_id=user_id,
        key_hash=hashed_key,
        name=name,
    )
    db.add(api_key)
    await db.flush()
    await db.refresh(api_key)

    return api_key, plain_key


async def find_api_key_by_plain_key(
    db: AsyncSession,
    plain_key: str,
) -> Optional[ApiKey]:
    """
    Find an API key by verifying the plain key against stored hashes.

    Note: This is O(n) where n is number of active API keys.
    For large scale, consider using a key prefix for faster lookup.

    Args:
        db: Database session
        plain_key: Plain API key from request

    Returns:
        ApiKey if found and valid, None otherwise
    """
    # Get all active API keys
    result = await db.execute(
        select(ApiKey).where(ApiKey.is_active == True)
    )
    api_keys = result.scalars().all()

    # Check each key (bcrypt verification is slow but secure)
    for api_key in api_keys:
        if verify_api_key(plain_key, api_key.key_hash):
            return api_key

    return None


async def update_api_key_last_used(db: AsyncSession, api_key: ApiKey) -> None:
    """
    Update the last_used_at timestamp for an API key.

    Args:
        db: Database session
        api_key: ApiKey instance to update
    """
    api_key.last_used_at = datetime.utcnow()
    await db.flush()


async def revoke_api_key(db: AsyncSession, api_key: ApiKey) -> None:
    """
    Revoke an API key by setting is_active to False.

    Args:
        db: Database session
        api_key: ApiKey instance to revoke
    """
    api_key.is_active = False
    await db.flush()

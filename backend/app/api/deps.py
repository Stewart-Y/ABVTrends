"""
ABVTrends - API Dependencies

FastAPI dependency injection for authentication and authorization.
"""

from typing import Optional
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.user import User, UserRole
from app.services.auth import (
    decode_token,
    find_api_key_by_plain_key,
    get_user_by_id,
    update_api_key_last_used,
)

# HTTP Bearer token scheme (for JWT)
# auto_error=False allows us to handle missing tokens gracefully
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Get the current authenticated user from JWT token.

    This dependency extracts the JWT from the Authorization header,
    validates it, and returns the associated user.

    Raises:
        HTTPException 401: If token is missing, invalid, or user not found
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Decode and validate the token
    payload = decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get user from database
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user = await get_user_by_id(db, UUID(user_id))
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID in token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is disabled",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def get_current_user_or_api_key(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    x_api_key: Optional[str] = Header(None, alias=settings.api_key_header),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Authenticate via JWT token OR API key.

    This dependency first checks for an API key in the X-API-Key header.
    If not present, it falls back to JWT authentication.

    Raises:
        HTTPException 401: If neither method succeeds
    """
    # Try API key first (if provided)
    if x_api_key:
        api_key = await find_api_key_by_plain_key(db, x_api_key)
        if api_key and api_key.is_active:
            # Update last used timestamp
            await update_api_key_last_used(db, api_key)

            # Get the user associated with this API key
            user = await get_user_by_id(db, api_key.user_id)
            if user and user.is_active:
                return user

        # API key provided but invalid
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    # Fall back to JWT authentication
    return await get_current_user(credentials, db)


async def require_admin(
    user: User = Depends(get_current_user_or_api_key),
) -> User:
    """
    Require admin role for access.

    This dependency should be used for admin-only endpoints.

    Raises:
        HTTPException 403: If user is not an admin
    """
    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    x_api_key: Optional[str] = Header(None, alias=settings.api_key_header),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """
    Optionally get the current user if authenticated.

    This dependency returns the user if authentication is provided and valid,
    or None if no authentication is provided. Useful for public endpoints
    that may behave differently for authenticated users.

    Note: Invalid credentials will still return None (not raise an error).
    """
    # Try API key first
    if x_api_key:
        api_key = await find_api_key_by_plain_key(db, x_api_key)
        if api_key and api_key.is_active:
            await update_api_key_last_used(db, api_key)
            user = await get_user_by_id(db, api_key.user_id)
            if user and user.is_active:
                return user
        return None

    # Try JWT
    if not credentials:
        return None

    payload = decode_token(credentials.credentials)
    if not payload:
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    try:
        user = await get_user_by_id(db, UUID(user_id))
    except ValueError:
        return None

    if user and user.is_active:
        return user

    return None

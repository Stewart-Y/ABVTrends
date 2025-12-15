"""
ABVTrends API - Authentication Endpoints

User registration, login, and API key management.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.auth import (
    ApiKeyCreate,
    ApiKeyInfo,
    ApiKeyListItem,
    ApiKeyListResponse,
    ApiKeyResponse,
    LoginRequest,
    TokenResponse,
    UserCreate,
    UserInfo,
    UserResponse,
)
from app.services.auth import (
    authenticate_user,
    create_access_token,
    create_api_key,
    create_user,
    get_api_key_by_id,
    get_user_api_keys,
    get_user_by_email,
    revoke_api_key,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


# =============================================================================
# User Registration & Login
# =============================================================================


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    data: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Register a new user account.

    Creates a new user with the provided email and password.
    The password is hashed before storage.
    """
    # Check if email already exists
    existing_user = await get_user_by_email(db, data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Create the user
    user = await create_user(db, email=data.email, password=data.password)

    logger.info(f"New user registered: {user.email}")

    return UserResponse(
        id=user.id,
        email=user.email,
        role=user.role.value,
        is_active=user.is_active,
        created_at=user.created_at,
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    data: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Authenticate and get a JWT access token.

    Provide email and password to receive a JWT token for API access.
    The token should be included in subsequent requests as:
    `Authorization: Bearer <token>`
    """
    # Authenticate user
    user = await authenticate_user(db, email=data.email, password=data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Generate access token
    access_token, expires_in = create_access_token(user.id, user.role)

    logger.info(f"User logged in: {user.email}")

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_in,
        user=UserInfo(
            id=user.id,
            email=user.email,
            role=user.role.value,
            is_active=user.is_active,
        ),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(
    user: User = Depends(get_current_user),
):
    """
    Get current user information.

    Returns the profile of the currently authenticated user.
    """
    return UserResponse(
        id=user.id,
        email=user.email,
        role=user.role.value,
        is_active=user.is_active,
        created_at=user.created_at,
    )


# =============================================================================
# API Key Management
# =============================================================================


@router.post("/api-keys", response_model=ApiKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key_endpoint(
    data: ApiKeyCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new API key.

    Creates a new API key for programmatic access to the API.

    **Important:** The returned `key` value is only shown once.
    Store it securely as it cannot be retrieved later.

    Use the key in requests with the header:
    `X-API-Key: <your-key>`
    """
    api_key, plain_key = await create_api_key(db, user_id=user.id, name=data.name)

    logger.info(f"API key created: {api_key.name} for user {user.email}")

    return ApiKeyResponse(
        api_key=ApiKeyInfo(
            id=api_key.id,
            name=api_key.name,
            created_at=api_key.created_at,
        ),
        key=plain_key,  # Only time this is shown!
    )


@router.get("/api-keys", response_model=ApiKeyListResponse)
async def list_api_keys(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List all API keys for the current user.

    Returns metadata about all API keys. The actual key values
    are not returned as they are only shown once upon creation.
    """
    api_keys = await get_user_api_keys(db, user.id)

    return ApiKeyListResponse(
        api_keys=[
            ApiKeyListItem(
                id=key.id,
                name=key.name,
                is_active=key.is_active,
                last_used_at=key.last_used_at,
                created_at=key.created_at,
            )
            for key in api_keys
        ],
        total=len(api_keys),
    )


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_200_OK)
async def revoke_api_key_endpoint(
    key_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Revoke an API key.

    Permanently deactivates the API key. This cannot be undone.
    The key will no longer be usable for authentication.
    """
    api_key = await get_api_key_by_id(db, key_id=key_id, user_id=user.id)

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )

    if not api_key.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="API key is already revoked",
        )

    await revoke_api_key(db, api_key)

    logger.info(f"API key revoked: {api_key.name} for user {user.email}")

    return {"message": "API key revoked successfully"}

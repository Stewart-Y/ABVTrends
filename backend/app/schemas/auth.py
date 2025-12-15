"""
ABVTrends - Authentication Schemas

Pydantic models for authentication requests and responses.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# =============================================================================
# Request Schemas
# =============================================================================


class UserCreate(BaseModel):
    """Schema for user registration."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=100)


class LoginRequest(BaseModel):
    """Schema for login request."""

    email: EmailStr
    password: str


class ApiKeyCreate(BaseModel):
    """Schema for creating a new API key."""

    name: str = Field(min_length=1, max_length=100)


# =============================================================================
# Response Schemas
# =============================================================================


class UserInfo(BaseModel):
    """Schema for user info in token response."""

    id: UUID
    email: str
    role: str
    is_active: bool


class TokenResponse(BaseModel):
    """Schema for JWT token response."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds until expiration
    user: UserInfo


class UserResponse(BaseModel):
    """Schema for user information response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    role: str
    is_active: bool
    created_at: datetime


class ApiKeyInfo(BaseModel):
    """Schema for API key metadata."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    created_at: datetime


class ApiKeyResponse(BaseModel):
    """Schema for newly created API key response.

    Note: The `key` field is only returned once upon creation.
    Store it securely as it cannot be retrieved later.
    """

    api_key: ApiKeyInfo
    key: str  # Plain key - only shown once!


class ApiKeyListItem(BaseModel):
    """Schema for API key in list response (without the actual key)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    is_active: bool
    last_used_at: Optional[datetime]
    created_at: datetime


class ApiKeyListResponse(BaseModel):
    """Schema for list of API keys response."""

    api_keys: list[ApiKeyListItem]
    total: int


# =============================================================================
# Error Schemas
# =============================================================================


class AuthError(BaseModel):
    """Schema for authentication error response."""

    detail: str
    code: str = "auth_error"

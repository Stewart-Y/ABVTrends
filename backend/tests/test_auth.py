"""
ABVTrends - Authentication Tests

Unit tests for authentication and authorization functionality.
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4

from app.services.auth import (
    hash_password,
    verify_password,
    create_access_token,
    decode_token,
    generate_api_key,
    verify_api_key,
)
from app.models.user import UserRole


class TestPasswordHashing:
    """Tests for password hashing functionality."""

    def test_hash_password_returns_different_value(self):
        """Password hash should be different from plain text."""
        password = "SecurePassword123!"
        hashed = hash_password(password)
        assert hashed != password
        assert len(hashed) > 50  # bcrypt hashes are ~60 chars

    def test_hash_password_produces_unique_hashes(self):
        """Same password should produce different hashes (salt)."""
        password = "SecurePassword123!"
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        assert hash1 != hash2  # Different salts

    def test_verify_password_correct(self):
        """Correct password should verify successfully."""
        password = "SecurePassword123!"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """Incorrect password should fail verification."""
        password = "SecurePassword123!"
        wrong_password = "WrongPassword456!"
        hashed = hash_password(password)
        assert verify_password(wrong_password, hashed) is False

    def test_verify_password_empty_string(self):
        """Empty password should fail verification."""
        password = "SecurePassword123!"
        hashed = hash_password(password)
        assert verify_password("", hashed) is False

    def test_hash_empty_password(self):
        """Hashing empty password should work (validation elsewhere)."""
        hashed = hash_password("")
        assert hashed is not None
        assert len(hashed) > 0


class TestJWTTokens:
    """Tests for JWT token creation and validation."""

    def test_create_access_token_structure(self):
        """Access token should be a valid JWT string."""
        user_id = uuid4()
        token, expires_in = create_access_token(user_id, UserRole.USER)

        assert isinstance(token, str)
        assert len(token) > 50
        assert token.count(".") == 2  # JWT has 3 parts
        assert isinstance(expires_in, int)
        assert expires_in > 0

    def test_create_access_token_includes_claims(self):
        """Token should contain correct claims."""
        user_id = uuid4()
        role = UserRole.ADMIN
        token, _ = create_access_token(user_id, role)

        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == str(user_id)
        assert payload["role"] == role.value
        assert "exp" in payload
        assert "iat" in payload

    def test_decode_valid_token(self):
        """Valid token should decode successfully."""
        user_id = uuid4()
        token, _ = create_access_token(user_id, UserRole.USER)

        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == str(user_id)

    def test_decode_invalid_token(self):
        """Invalid token should return None."""
        invalid_token = "not.a.valid.jwt.token"
        payload = decode_token(invalid_token)
        assert payload is None

    def test_decode_malformed_token(self):
        """Malformed token should return None."""
        malformed = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.invalid"
        payload = decode_token(malformed)
        assert payload is None

    def test_decode_empty_token(self):
        """Empty token should return None."""
        payload = decode_token("")
        assert payload is None

    def test_token_expires_in_correct_range(self):
        """Token expiry should match configured duration."""
        user_id = uuid4()
        _, expires_in = create_access_token(user_id, UserRole.USER)

        # Default is 24 hours = 86400 seconds
        assert expires_in == 86400

    def test_different_users_get_different_tokens(self):
        """Different users should get unique tokens."""
        user1 = uuid4()
        user2 = uuid4()

        token1, _ = create_access_token(user1, UserRole.USER)
        token2, _ = create_access_token(user2, UserRole.USER)

        assert token1 != token2

    def test_role_included_in_token(self):
        """User role should be included in token payload."""
        user_id = uuid4()

        admin_token, _ = create_access_token(user_id, UserRole.ADMIN)
        user_token, _ = create_access_token(user_id, UserRole.USER)

        admin_payload = decode_token(admin_token)
        user_payload = decode_token(user_token)

        assert admin_payload["role"] == "admin"
        assert user_payload["role"] == "user"


class TestAPIKeys:
    """Tests for API key generation and validation."""

    def test_generate_api_key_format(self):
        """Generated API key should have correct format."""
        plain_key, hashed_key = generate_api_key()

        # Plain key starts with prefix
        assert plain_key.startswith("abv_")
        assert len(plain_key) > 40

        # Hashed key should be bcrypt hash
        assert hashed_key != plain_key
        assert len(hashed_key) > 50

    def test_generate_unique_api_keys(self):
        """Each call should generate unique keys."""
        key1, hash1 = generate_api_key()
        key2, hash2 = generate_api_key()

        assert key1 != key2
        assert hash1 != hash2

    def test_verify_api_key_correct(self):
        """Valid API key should verify successfully."""
        plain_key, hashed_key = generate_api_key()
        assert verify_api_key(plain_key, hashed_key) is True

    def test_verify_api_key_incorrect(self):
        """Invalid API key should fail verification."""
        plain_key, hashed_key = generate_api_key()
        wrong_key = "abv_wrongkey12345"
        assert verify_api_key(wrong_key, hashed_key) is False

    def test_verify_api_key_empty(self):
        """Empty API key should fail verification."""
        _, hashed_key = generate_api_key()
        assert verify_api_key("", hashed_key) is False

    def test_api_key_prefix_consistent(self):
        """All generated keys should have same prefix."""
        for _ in range(5):
            plain_key, _ = generate_api_key()
            assert plain_key.startswith("abv_")


class TestUserRoles:
    """Tests for user role enumeration."""

    def test_user_role_values(self):
        """User roles should have correct string values."""
        assert UserRole.ADMIN.value == "admin"
        assert UserRole.USER.value == "user"

    def test_user_role_from_string(self):
        """Should be able to create role from string."""
        admin = UserRole("admin")
        user = UserRole("user")
        assert admin == UserRole.ADMIN
        assert user == UserRole.USER

    def test_invalid_role_raises(self):
        """Invalid role string should raise ValueError."""
        with pytest.raises(ValueError):
            UserRole("superadmin")


class TestTokenExpiration:
    """Tests for token expiration handling."""

    def test_token_contains_expiration(self):
        """Token payload should contain expiration time."""
        user_id = uuid4()
        token, _ = create_access_token(user_id, UserRole.USER)

        payload = decode_token(token)
        assert "exp" in payload
        assert isinstance(payload["exp"], int)

    def test_token_expiration_in_future(self):
        """Token expiration should be in the future."""
        user_id = uuid4()
        token, _ = create_access_token(user_id, UserRole.USER)

        payload = decode_token(token)
        exp_time = datetime.utcfromtimestamp(payload["exp"])
        now = datetime.utcnow()

        assert exp_time > now

    def test_token_issued_at_present(self):
        """Token issue time should be approximately now."""
        user_id = uuid4()
        token, _ = create_access_token(user_id, UserRole.USER)

        payload = decode_token(token)
        iat_time = datetime.utcfromtimestamp(payload["iat"])
        now = datetime.utcnow()

        # Should be within 5 seconds
        assert abs((now - iat_time).total_seconds()) < 5

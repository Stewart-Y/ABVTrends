"""
ABVTrends - Test Configuration

Shared fixtures and configuration for pytest.
"""

import os
import pytest
from unittest.mock import patch, MagicMock

# Set test environment before importing app modules
os.environ["ENVIRONMENT"] = "test"
os.environ["DEBUG"] = "false"
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test_db"
os.environ["REDIS_URL"] = "redis://localhost:6379/1"
os.environ["SECRET_KEY"] = "test-secret-key-do-not-use-in-production"


@pytest.fixture
def mock_settings():
    """Provide mock settings for testing."""
    from app.core.config import Settings

    return Settings(
        environment="test",
        debug=False,
        database_url="postgresql://test:test@localhost:5432/test_db",
        db_ssl_required=False,
        allowed_origins="http://localhost:3000,https://test.example.com",
    )


@pytest.fixture
def test_client():
    """Create a test client for the FastAPI app."""
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as client:
        yield client


@pytest.fixture
def mock_db_session():
    """Mock database session for testing."""
    session = MagicMock()
    session.commit = MagicMock()
    session.rollback = MagicMock()
    session.close = MagicMock()
    return session

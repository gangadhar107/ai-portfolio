"""
Shared fixtures for route tests.
"""

import os
import hmac
import hashlib

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


@pytest.fixture(scope="session", autouse=True)
def _set_env():
    """Ensure env vars are set before app import."""
    os.environ.setdefault("SESSION_SECRET_KEY", "testsecretkey12345678901234567890")
    os.environ.setdefault("DASHBOARD_PASSWORD", "testpass")
    os.environ.setdefault("DATABASE_URL", "postgresql://unused:unused@localhost/unused")
    os.environ.setdefault("GROQ_API_KEY", "test-groq-key")


@pytest.fixture()
def valid_auth_cookie():
    """Return the valid auth cookie value matching the app's SESSION_TOKEN."""
    from routers.tracking import SESSION_TOKEN
    return SESSION_TOKEN


@pytest.fixture()
def invalid_auth_cookie():
    return "invalid_garbage_token_000"


@pytest.fixture()
def client():
    """FastAPI TestClient with all DB/service calls mocked."""
    from main import app
    return TestClient(app, raise_server_exceptions=False)

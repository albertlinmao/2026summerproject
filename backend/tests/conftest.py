import pytest
import asyncio
from typing import AsyncGenerator
from httpx import AsyncClient
from src.main import app


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client for the FastAPI app."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.fixture
def mock_supabase():
    """Mock Supabase client for testing."""
    from unittest.mock import MagicMock
    return MagicMock()


@pytest.fixture
def mock_redis():
    """Mock Redis client for testing."""
    from unittest.mock import MagicMock
    return MagicMock()


@pytest.fixture
def sample_athlete():
    """Sample athlete data for testing."""
    return {
        "id": "test-athlete-uuid",
        "club_id": "test-club-uuid",
        "name": "Test Athlete",
    }


@pytest.fixture
def sample_coach():
    """Sample coach data for testing."""
    return {
        "id": "test-coach-uuid",
        "club_id": "test-club-uuid",
        "name": "Test Coach",
    }


@pytest.fixture
def sample_club():
    """Sample club data for testing."""
    return {
        "id": "test-club-uuid",
        "name": "Test Club",
    }
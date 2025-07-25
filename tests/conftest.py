"""Pytest configuration and shared fixtures."""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, MagicMock
from datetime import datetime
from typing import Dict, List

import pytest


@pytest.fixture
def mock_raindrop_token():
    """Mock Raindrop API token."""
    return "test_raindrop_token_123"


@pytest.fixture
def mock_collections():
    """Mock collection data."""
    return [
        {"_id": 1, "title": "Unsorted", "count": 25},
        {"_id": 2, "title": "Development", "count": 150},
        {"_id": 3, "title": "Gaming", "count": 75},
        {"_id": 4, "title": "Archive", "count": 500},
    ]


@pytest.fixture
def mock_bookmarks():
    """Mock bookmark data."""
    return [
        {
            "_id": 101,
            "title": "Python Tutorial - Learn Python Programming",
            "link": "https://python.org/tutorial",
            "domain": "python.org",
            "excerpt": "Learn Python programming with this comprehensive tutorial",
            "created": "2024-01-15T10:30:00Z",
        },
        {
            "_id": 102,
            "title": "Metroid Prime Speedrun Guide",
            "link": "https://speedrun.com/metroidprime/guide",
            "domain": "speedrun.com",
            "excerpt": "Complete guide to speedrunning Metroid Prime",
            "created": "2024-01-10T15:45:00Z",
        },
        {
            "_id": 103,
            "title": "Old React Tutorial from 2019",
            "link": "https://example.com/react-tutorial-2019",
            "domain": "example.com",
            "excerpt": "Outdated React tutorial using class components",
            "created": "2019-03-20T08:15:00Z",
        },
    ]


@pytest.fixture
def mock_claude_decisions():
    """Mock Claude AI decision responses."""
    return [
        {
            "action": "MOVE",
            "target": "Development",
            "reasoning": "programming tutorial",
        },
        {"action": "MOVE", "target": "Gaming", "reasoning": "game speedrun guide"},
        {"action": "DELETE", "reasoning": "outdated tutorial"},
    ]


@pytest.fixture
def temp_state_dir():
    """Create temporary directory for state files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def mock_anthropic_client():
    """Mock Anthropic client."""
    mock_client = Mock()
    mock_message = Mock()
    mock_message.content = [Mock()]
    mock_message.content[
        0
    ].text = """1. MOVE:Development - programming tutorial
2. MOVE:Gaming - game speedrun guide  
3. DELETE - outdated tutorial"""

    mock_client.messages.create.return_value = mock_message
    return mock_client


@pytest.fixture
def mock_requests_get():
    """Mock requests.get for API calls."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"items": []}
    return mock_response


@pytest.fixture
def mock_requests_delete():
    """Mock requests.delete for API calls."""
    mock_response = Mock()
    mock_response.status_code = 200
    return mock_response


@pytest.fixture
def mock_requests_put():
    """Mock requests.put for API calls."""
    mock_response = Mock()
    mock_response.status_code = 200
    return mock_response


@pytest.fixture
def sample_state_data():
    """Sample state data for testing."""
    return {
        "collection_id": 1,
        "collection_name": "Unsorted",
        "current_page": 2,
        "processed_bookmark_ids": [101, 102, 103],
        "stats": {
            "processed": 3,
            "kept": 1,
            "deleted": 1,
            "archived": 0,
            "moved": 1,
            "errors": 0,
            "skipped": 0,
            "start_time": datetime.now().isoformat(),
            "session_time": 300.0,
        },
        "last_updated": datetime.now().isoformat(),
        "dry_run": False,
    }


@pytest.fixture
def mock_curses():
    """Mock curses module for UI testing."""
    mock_curses = Mock()
    mock_stdscr = Mock()
    mock_stdscr.getmaxyx.return_value = (24, 80)
    mock_stdscr.getch.side_effect = [ord("\n")]  # Simulate Enter key

    mock_curses.wrapper.return_value = []
    mock_curses.A_BOLD = 1
    mock_curses.A_REVERSE = 2
    mock_curses.A_NORMAL = 0
    mock_curses.KEY_UP = 259
    mock_curses.KEY_DOWN = 258
    mock_curses.KEY_LEFT = 260
    mock_curses.KEY_RIGHT = 261

    return mock_curses


# Test data helpers
def create_mock_bookmark(
    bookmark_id: int, title: str, domain: str = "example.com"
) -> Dict:
    """Create a mock bookmark for testing."""
    return {
        "_id": bookmark_id,
        "title": title,
        "link": f"https://{domain}/page{bookmark_id}",
        "domain": domain,
        "excerpt": f"Sample excerpt for {title}",
        "created": "2024-01-15T10:30:00Z",
    }


def create_mock_collection(collection_id: int, title: str, count: int = 10) -> Dict:
    """Create a mock collection for testing."""
    return {"_id": collection_id, "title": title, "count": count}

"""Shared fixtures for RAG system tests."""
import pytest
from unittest.mock import Mock, MagicMock
from dataclasses import dataclass
import sys
import os

# Add backend to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vector_store import SearchResults


@dataclass
class MockConfig:
    """Mock configuration for testing."""
    ANTHROPIC_API_KEY: str = "test-api-key"
    ANTHROPIC_MODEL: str = "claude-sonnet-4-20250514"
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 100
    MAX_RESULTS: int = 5
    MAX_HISTORY: int = 2
    CHROMA_PATH: str = "./test_chroma_db"


@pytest.fixture
def mock_config():
    """Provide mock configuration."""
    return MockConfig()


@pytest.fixture
def mock_vector_store():
    """Create a mock VectorStore with common behaviors."""
    store = Mock()

    # Default search returns empty results
    store.search.return_value = SearchResults(
        documents=[],
        metadata=[],
        distances=[]
    )

    # Default course resolution
    store._resolve_course_name.return_value = None
    store.get_lesson_link.return_value = None
    store.get_course_outline.return_value = None

    return store


@pytest.fixture
def sample_search_results():
    """Provide sample search results for testing."""
    return SearchResults(
        documents=[
            "RAG stands for Retrieval-Augmented Generation. It combines retrieval with generation.",
            "The MCP protocol allows tools to communicate with AI models effectively."
        ],
        metadata=[
            {"course_title": "Introduction to RAG", "lesson_number": 1},
            {"course_title": "MCP Course", "lesson_number": 3}
        ],
        distances=[0.2, 0.4]
    )


@pytest.fixture
def sample_course_outline():
    """Provide sample course outline for testing."""
    return {
        "title": "MCP: Build Rich-Context AI Apps",
        "course_link": "https://example.com/mcp-course",
        "lessons": [
            {"lesson_number": 0, "lesson_title": "Introduction", "lesson_link": "https://example.com/lesson0"},
            {"lesson_number": 1, "lesson_title": "Getting Started", "lesson_link": "https://example.com/lesson1"},
            {"lesson_number": 2, "lesson_title": "Advanced Topics", "lesson_link": "https://example.com/lesson2"}
        ]
    }


@pytest.fixture
def mock_anthropic_client():
    """Create a mock Anthropic client."""
    client = Mock()
    return client

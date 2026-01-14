"""Shared fixtures for RAG system tests."""
import pytest
from unittest.mock import Mock, MagicMock, patch
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


# ============================================================
# API Testing Fixtures
# ============================================================

@pytest.fixture
def mock_rag_system():
    """Create a mock RAGSystem for API testing."""
    rag = Mock()

    # Mock session manager
    rag.session_manager = Mock()
    rag.session_manager.create_session.return_value = "test-session-123"
    rag.session_manager.clear_session.return_value = None

    # Mock query method
    rag.query.return_value = (
        "This is a test response about RAG systems.",
        [{"text": "Introduction to RAG - Lesson 1", "url": "https://example.com/lesson1"}]
    )

    # Mock analytics
    rag.get_course_analytics.return_value = {
        "total_courses": 3,
        "course_titles": ["Introduction to RAG", "MCP Course", "Advanced AI"]
    }

    return rag


@pytest.fixture
def test_app(mock_rag_system):
    """
    Create a test FastAPI app with mocked dependencies.

    This creates a standalone test app to avoid static file mounting issues
    from the production app.py which requires the frontend directory.
    """
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel
    from typing import List, Optional

    # Create a minimal test app with only the API endpoints
    app = FastAPI(title="Test RAG API")

    # Request/Response models (matching production app)
    class QueryRequest(BaseModel):
        query: str
        session_id: Optional[str] = None

    class QueryResponse(BaseModel):
        answer: str
        sources: List[dict]
        session_id: str

    class CourseStats(BaseModel):
        total_courses: int
        course_titles: List[str]

    # Store mock in app state for access in endpoints
    app.state.rag_system = mock_rag_system

    @app.post("/api/query", response_model=QueryResponse)
    async def query_documents(request: QueryRequest):
        try:
            rag = app.state.rag_system
            session_id = request.session_id
            if not session_id:
                session_id = rag.session_manager.create_session()

            answer, sources = rag.query(request.query, session_id)

            return QueryResponse(
                answer=answer,
                sources=sources,
                session_id=session_id
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/courses", response_model=CourseStats)
    async def get_course_stats():
        try:
            rag = app.state.rag_system
            analytics = rag.get_course_analytics()
            return CourseStats(
                total_courses=analytics["total_courses"],
                course_titles=analytics["course_titles"]
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.delete("/api/session/{session_id}")
    async def clear_session(session_id: str):
        try:
            rag = app.state.rag_system
            rag.session_manager.clear_session(session_id)
            return {"status": "ok", "message": "Session cleared"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/")
    async def root():
        return {"message": "RAG API is running"}

    return app


@pytest.fixture
def test_client(test_app):
    """Create an async test client for the test app."""
    from httpx import AsyncClient, ASGITransport

    transport = ASGITransport(app=test_app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
def sample_query_request():
    """Provide a sample query request payload."""
    return {
        "query": "What is RAG?",
        "session_id": None
    }


@pytest.fixture
def sample_query_request_with_session():
    """Provide a sample query request with session ID."""
    return {
        "query": "Tell me more about that topic",
        "session_id": "existing-session-456"
    }

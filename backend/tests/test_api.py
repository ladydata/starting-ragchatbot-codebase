"""Tests for FastAPI endpoints."""
import pytest
from unittest.mock import Mock


class TestQueryEndpoint:
    """Test suite for POST /api/query endpoint."""

    async def test_query_returns_200_with_valid_request(self, test_client, sample_query_request):
        """Test successful query returns 200 status."""
        async with test_client as client:
            response = await client.post("/api/query", json=sample_query_request)

        assert response.status_code == 200

    async def test_query_returns_answer_in_response(self, test_client, sample_query_request):
        """Test that response contains an answer field."""
        async with test_client as client:
            response = await client.post("/api/query", json=sample_query_request)

        data = response.json()
        assert "answer" in data
        assert data["answer"] == "This is a test response about RAG systems."

    async def test_query_returns_sources_in_response(self, test_client, sample_query_request):
        """Test that response contains sources field."""
        async with test_client as client:
            response = await client.post("/api/query", json=sample_query_request)

        data = response.json()
        assert "sources" in data
        assert isinstance(data["sources"], list)
        assert len(data["sources"]) == 1
        assert data["sources"][0]["text"] == "Introduction to RAG - Lesson 1"

    async def test_query_creates_session_when_not_provided(self, test_client, test_app):
        """Test that a new session is created when not provided."""
        async with test_client as client:
            response = await client.post("/api/query", json={"query": "test"})

        data = response.json()
        assert "session_id" in data
        assert data["session_id"] == "test-session-123"

        # Verify session manager was called
        test_app.state.rag_system.session_manager.create_session.assert_called_once()

    async def test_query_uses_provided_session_id(self, test_client, test_app, sample_query_request_with_session):
        """Test that provided session ID is used."""
        async with test_client as client:
            response = await client.post("/api/query", json=sample_query_request_with_session)

        data = response.json()
        assert data["session_id"] == "existing-session-456"

        # Verify query was called with the session ID
        test_app.state.rag_system.query.assert_called_with(
            "Tell me more about that topic",
            "existing-session-456"
        )

    async def test_query_calls_rag_system(self, test_client, test_app, sample_query_request):
        """Test that query endpoint calls RAG system."""
        async with test_client as client:
            await client.post("/api/query", json=sample_query_request)

        test_app.state.rag_system.query.assert_called_once()

    async def test_query_returns_422_for_missing_query(self, test_client):
        """Test that missing query field returns 422 validation error."""
        async with test_client as client:
            response = await client.post("/api/query", json={})

        assert response.status_code == 422

    async def test_query_returns_500_on_rag_error(self, test_client, test_app):
        """Test that RAG system errors return 500."""
        test_app.state.rag_system.query.side_effect = Exception("Database error")

        async with test_client as client:
            response = await client.post("/api/query", json={"query": "test"})

        assert response.status_code == 500
        assert "Database error" in response.json()["detail"]


class TestCoursesEndpoint:
    """Test suite for GET /api/courses endpoint."""

    async def test_courses_returns_200(self, test_client):
        """Test successful courses request returns 200."""
        async with test_client as client:
            response = await client.get("/api/courses")

        assert response.status_code == 200

    async def test_courses_returns_total_count(self, test_client):
        """Test that response contains total course count."""
        async with test_client as client:
            response = await client.get("/api/courses")

        data = response.json()
        assert "total_courses" in data
        assert data["total_courses"] == 3

    async def test_courses_returns_course_titles(self, test_client):
        """Test that response contains course titles list."""
        async with test_client as client:
            response = await client.get("/api/courses")

        data = response.json()
        assert "course_titles" in data
        assert isinstance(data["course_titles"], list)
        assert len(data["course_titles"]) == 3
        assert "Introduction to RAG" in data["course_titles"]

    async def test_courses_calls_analytics(self, test_client, test_app):
        """Test that courses endpoint calls get_course_analytics."""
        async with test_client as client:
            await client.get("/api/courses")

        test_app.state.rag_system.get_course_analytics.assert_called_once()

    async def test_courses_returns_500_on_error(self, test_client, test_app):
        """Test that analytics errors return 500."""
        test_app.state.rag_system.get_course_analytics.side_effect = Exception("Analytics error")

        async with test_client as client:
            response = await client.get("/api/courses")

        assert response.status_code == 500
        assert "Analytics error" in response.json()["detail"]


class TestSessionEndpoint:
    """Test suite for DELETE /api/session/{session_id} endpoint."""

    async def test_clear_session_returns_200(self, test_client):
        """Test successful session clear returns 200."""
        async with test_client as client:
            response = await client.delete("/api/session/test-session")

        assert response.status_code == 200

    async def test_clear_session_returns_ok_status(self, test_client):
        """Test that response contains ok status."""
        async with test_client as client:
            response = await client.delete("/api/session/test-session")

        data = response.json()
        assert data["status"] == "ok"
        assert "message" in data

    async def test_clear_session_calls_session_manager(self, test_client, test_app):
        """Test that clear session calls session manager."""
        async with test_client as client:
            await client.delete("/api/session/my-session-123")

        test_app.state.rag_system.session_manager.clear_session.assert_called_with("my-session-123")

    async def test_clear_session_returns_500_on_error(self, test_client, test_app):
        """Test that session errors return 500."""
        test_app.state.rag_system.session_manager.clear_session.side_effect = Exception("Session error")

        async with test_client as client:
            response = await client.delete("/api/session/bad-session")

        assert response.status_code == 500
        assert "Session error" in response.json()["detail"]


class TestRootEndpoint:
    """Test suite for GET / endpoint."""

    async def test_root_returns_200(self, test_client):
        """Test root endpoint returns 200."""
        async with test_client as client:
            response = await client.get("/")

        assert response.status_code == 200

    async def test_root_returns_running_message(self, test_client):
        """Test root endpoint returns running status."""
        async with test_client as client:
            response = await client.get("/")

        data = response.json()
        assert "message" in data
        assert "running" in data["message"].lower()


class TestQueryResponseFormat:
    """Test suite for query response format validation."""

    async def test_response_has_required_fields(self, test_client, sample_query_request):
        """Test that response contains all required fields."""
        async with test_client as client:
            response = await client.post("/api/query", json=sample_query_request)

        data = response.json()
        required_fields = ["answer", "sources", "session_id"]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

    async def test_sources_have_correct_structure(self, test_client, sample_query_request):
        """Test that sources have text and url fields."""
        async with test_client as client:
            response = await client.post("/api/query", json=sample_query_request)

        data = response.json()
        for source in data["sources"]:
            assert "text" in source
            assert "url" in source


class TestEmptyStates:
    """Test suite for edge cases with empty data."""

    async def test_query_with_empty_sources(self, test_client, test_app):
        """Test query response with no sources."""
        test_app.state.rag_system.query.return_value = ("No relevant content found.", [])

        async with test_client as client:
            response = await client.post("/api/query", json={"query": "obscure topic"})

        data = response.json()
        assert data["sources"] == []
        assert data["answer"] == "No relevant content found."

    async def test_courses_with_empty_catalog(self, test_client, test_app):
        """Test courses endpoint with no courses loaded."""
        test_app.state.rag_system.get_course_analytics.return_value = {
            "total_courses": 0,
            "course_titles": []
        }

        async with test_client as client:
            response = await client.get("/api/courses")

        data = response.json()
        assert data["total_courses"] == 0
        assert data["course_titles"] == []

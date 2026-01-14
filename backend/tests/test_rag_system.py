"""Tests for RAG system content query handling."""
import pytest
from unittest.mock import Mock, MagicMock, patch
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vector_store import SearchResults


class MockContentBlock:
    """Mock for Anthropic content block."""
    def __init__(self, block_type, text=None, tool_name=None, tool_input=None, tool_id=None):
        self.type = block_type
        self.text = text
        self.name = tool_name
        self.input = tool_input or {}
        self.id = tool_id


class MockResponse:
    """Mock for Anthropic API response."""
    def __init__(self, content, stop_reason="end_turn"):
        self.content = content
        self.stop_reason = stop_reason


class TestRAGSystemQuery:
    """Test suite for RAG system query handling."""

    @pytest.fixture
    def mock_rag_system(self, mock_config, sample_search_results):
        """Create RAGSystem with mocked dependencies."""
        with patch('rag_system.VectorStore') as MockVectorStore, \
             patch('rag_system.AIGenerator') as MockAIGenerator, \
             patch('rag_system.DocumentProcessor') as MockDocProcessor, \
             patch('rag_system.SessionManager') as MockSessionManager:

            # Configure mock vector store
            mock_store = MockVectorStore.return_value
            mock_store.search.return_value = sample_search_results
            mock_store.get_lesson_link.return_value = "https://example.com/lesson"
            mock_store.get_course_outline.return_value = None
            mock_store.get_course_count.return_value = 4
            mock_store.get_existing_course_titles.return_value = ["Course 1", "Course 2"]

            # Configure mock AI generator
            mock_ai = MockAIGenerator.return_value
            mock_ai.generate_response.return_value = "This is the AI response about RAG."

            # Configure mock session manager
            mock_session = MockSessionManager.return_value
            mock_session.get_conversation_history.return_value = None

            from rag_system import RAGSystem
            rag = RAGSystem(mock_config)

            # Expose mocks for assertions
            rag._mock_store = mock_store
            rag._mock_ai = mock_ai
            rag._mock_session = mock_session

            return rag

    def test_query_returns_response_and_sources(self, mock_rag_system):
        """Test that query returns both response and sources."""
        response, sources = mock_rag_system.query("What is RAG?")

        assert response is not None
        assert isinstance(sources, list)

    def test_query_passes_tools_to_ai_generator(self, mock_rag_system):
        """Test that tools are passed to AI generator."""
        mock_rag_system.query("What is RAG?")

        call_args = mock_rag_system._mock_ai.generate_response.call_args
        assert "tools" in call_args.kwargs
        assert call_args.kwargs["tools"] is not None

    def test_query_passes_tool_manager_to_ai_generator(self, mock_rag_system):
        """Test that tool manager is passed for tool execution."""
        mock_rag_system.query("What is RAG?")

        call_args = mock_rag_system._mock_ai.generate_response.call_args
        assert "tool_manager" in call_args.kwargs
        assert call_args.kwargs["tool_manager"] == mock_rag_system.tool_manager

    def test_query_formats_prompt_correctly(self, mock_rag_system):
        """Test that user query is formatted into prompt."""
        mock_rag_system.query("What is RAG?")

        call_args = mock_rag_system._mock_ai.generate_response.call_args
        query_arg = call_args.kwargs["query"]

        assert "What is RAG?" in query_arg
        assert "course materials" in query_arg.lower()

    def test_query_with_session_includes_history(self, mock_rag_system):
        """Test that session history is included when session_id provided."""
        mock_rag_system._mock_session.get_conversation_history.return_value = "Previous chat"

        mock_rag_system.query("Follow up question", session_id="session123")

        # Verify history was retrieved
        mock_rag_system._mock_session.get_conversation_history.assert_called_with("session123")

        # Verify history was passed to AI
        call_args = mock_rag_system._mock_ai.generate_response.call_args
        assert call_args.kwargs["conversation_history"] == "Previous chat"

    def test_query_updates_session_after_response(self, mock_rag_system):
        """Test that session is updated with new exchange."""
        mock_rag_system.query("What is RAG?", session_id="session456")

        mock_rag_system._mock_session.add_exchange.assert_called_once()
        call_args = mock_rag_system._mock_session.add_exchange.call_args
        assert call_args[0][0] == "session456"

    def test_query_retrieves_sources_from_tool_manager(self, mock_rag_system, sample_search_results):
        """Test that sources are retrieved from tool manager after query."""
        # Simulate tool execution that populates sources
        mock_rag_system.search_tool.last_sources = [
            {"text": "Course 1 - Lesson 1", "url": "https://example.com"}
        ]

        response, sources = mock_rag_system.query("What is RAG?")

        assert len(sources) == 1
        assert sources[0]["text"] == "Course 1 - Lesson 1"

    def test_query_resets_sources_after_retrieval(self, mock_rag_system):
        """Test that sources are reset after being retrieved."""
        mock_rag_system.search_tool.last_sources = [{"text": "Source", "url": None}]

        mock_rag_system.query("First question")

        # Sources should be reset
        assert mock_rag_system.search_tool.last_sources == []

    def test_query_without_session_skips_history(self, mock_rag_system):
        """Test that queries without session_id don't fetch history."""
        mock_rag_system.query("What is RAG?")

        # Should not update session
        mock_rag_system._mock_session.add_exchange.assert_not_called()


class TestRAGSystemToolRegistration:
    """Test suite for tool registration in RAG system."""

    @pytest.fixture
    def fresh_rag_system(self, mock_config):
        """Create RAGSystem with real tool registration."""
        with patch('rag_system.VectorStore') as MockVectorStore, \
             patch('rag_system.AIGenerator') as MockAIGenerator, \
             patch('rag_system.DocumentProcessor'), \
             patch('rag_system.SessionManager'):

            MockVectorStore.return_value.search.return_value = SearchResults([], [], [])

            from rag_system import RAGSystem
            return RAGSystem(mock_config)

    def test_search_tool_is_registered(self, fresh_rag_system):
        """Test that CourseSearchTool is registered."""
        tools = fresh_rag_system.tool_manager.get_tool_definitions()
        tool_names = [t["name"] for t in tools]

        assert "search_course_content" in tool_names

    def test_outline_tool_is_registered(self, fresh_rag_system):
        """Test that CourseOutlineTool is registered."""
        tools = fresh_rag_system.tool_manager.get_tool_definitions()
        tool_names = [t["name"] for t in tools]

        assert "get_course_outline" in tool_names

    def test_both_tools_available(self, fresh_rag_system):
        """Test that both tools are available."""
        tools = fresh_rag_system.tool_manager.get_tool_definitions()

        assert len(tools) == 2


class TestRAGSystemIntegration:
    """Integration tests for RAG system with real tool execution."""

    @pytest.fixture
    def integrated_rag_system(self, mock_config, sample_search_results):
        """Create RAGSystem with real tools but mocked external services."""
        with patch('rag_system.VectorStore') as MockVectorStore, \
             patch('rag_system.AIGenerator') as MockAIGenerator, \
             patch('rag_system.DocumentProcessor'), \
             patch('rag_system.SessionManager') as MockSessionManager:

            # Configure mock vector store
            mock_store = MockVectorStore.return_value
            mock_store.search.return_value = sample_search_results
            mock_store.get_lesson_link.return_value = "https://example.com/lesson"
            mock_store.get_course_outline.return_value = {
                "title": "Test Course",
                "course_link": "https://example.com",
                "lessons": [{"lesson_number": 0, "lesson_title": "Intro"}]
            }

            MockSessionManager.return_value.get_conversation_history.return_value = None

            from rag_system import RAGSystem
            rag = RAGSystem(mock_config)
            rag._mock_ai = MockAIGenerator.return_value
            rag._mock_store = mock_store

            return rag

    def test_tool_manager_can_execute_search(self, integrated_rag_system):
        """Test that tool manager can execute search tool."""
        result = integrated_rag_system.tool_manager.execute_tool(
            "search_course_content",
            query="What is RAG?"
        )

        assert "Introduction to RAG" in result or "RAG stands for" in result

    def test_tool_manager_can_execute_outline(self, integrated_rag_system):
        """Test that tool manager can execute outline tool."""
        result = integrated_rag_system.tool_manager.execute_tool(
            "get_course_outline",
            course_name="Test"
        )

        assert "Course: Test Course" in result
        assert "Lesson 0: Intro" in result

    def test_sources_flow_through_system(self, integrated_rag_system):
        """Test that sources from search flow through to response."""
        # Execute a search
        integrated_rag_system.tool_manager.execute_tool(
            "search_course_content",
            query="RAG"
        )

        # Get sources
        sources = integrated_rag_system.tool_manager.get_last_sources()

        assert len(sources) == 2
        assert any("Introduction to RAG" in s["text"] for s in sources)


class TestRAGSystemErrorHandling:
    """Test suite for error handling in RAG system."""

    @pytest.fixture
    def error_rag_system(self, mock_config):
        """Create RAGSystem configured to simulate errors."""
        with patch('rag_system.VectorStore') as MockVectorStore, \
             patch('rag_system.AIGenerator') as MockAIGenerator, \
             patch('rag_system.DocumentProcessor'), \
             patch('rag_system.SessionManager') as MockSessionManager:

            mock_store = MockVectorStore.return_value
            mock_store.search.return_value = SearchResults(
                documents=[],
                metadata=[],
                distances=[],
                error="Database connection failed"
            )

            MockSessionManager.return_value.get_conversation_history.return_value = None
            MockAIGenerator.return_value.generate_response.return_value = "Error occurred"

            from rag_system import RAGSystem
            rag = RAGSystem(mock_config)
            rag._mock_store = mock_store

            return rag

    def test_search_error_handled_gracefully(self, error_rag_system):
        """Test that search errors are handled gracefully."""
        result = error_rag_system.tool_manager.execute_tool(
            "search_course_content",
            query="test"
        )

        assert "Database connection failed" in result

    def test_empty_results_handled(self, mock_config):
        """Test handling of empty search results."""
        with patch('rag_system.VectorStore') as MockVectorStore, \
             patch('rag_system.AIGenerator'), \
             patch('rag_system.DocumentProcessor'), \
             patch('rag_system.SessionManager'):

            MockVectorStore.return_value.search.return_value = SearchResults([], [], [])

            from rag_system import RAGSystem
            rag = RAGSystem(mock_config)

            result = rag.tool_manager.execute_tool(
                "search_course_content",
                query="nonexistent topic"
            )

            assert "No relevant content found" in result

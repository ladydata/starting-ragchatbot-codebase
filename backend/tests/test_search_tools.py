"""Tests for CourseSearchTool execute method."""
import pytest
from unittest.mock import Mock
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from search_tools import CourseSearchTool, CourseOutlineTool, ToolManager
from vector_store import SearchResults


class TestCourseSearchToolExecute:
    """Test suite for CourseSearchTool.execute() method."""

    def test_execute_returns_formatted_results(self, mock_vector_store, sample_search_results):
        """Test that execute returns properly formatted search results."""
        mock_vector_store.search.return_value = sample_search_results
        mock_vector_store.get_lesson_link.return_value = "https://example.com/lesson"

        tool = CourseSearchTool(mock_vector_store)
        result = tool.execute(query="What is RAG?")

        # Verify search was called with correct parameters
        mock_vector_store.search.assert_called_once_with(
            query="What is RAG?",
            course_name=None,
            lesson_number=None
        )

        # Verify result contains course and lesson context
        assert "[Introduction to RAG - Lesson 1]" in result
        assert "[MCP Course - Lesson 3]" in result
        assert "RAG stands for Retrieval-Augmented Generation" in result

    def test_execute_with_course_filter(self, mock_vector_store, sample_search_results):
        """Test execute with course_name filter."""
        mock_vector_store.search.return_value = sample_search_results

        tool = CourseSearchTool(mock_vector_store)
        tool.execute(query="What is RAG?", course_name="MCP")

        mock_vector_store.search.assert_called_once_with(
            query="What is RAG?",
            course_name="MCP",
            lesson_number=None
        )

    def test_execute_with_lesson_filter(self, mock_vector_store, sample_search_results):
        """Test execute with lesson_number filter."""
        mock_vector_store.search.return_value = sample_search_results

        tool = CourseSearchTool(mock_vector_store)
        tool.execute(query="What is RAG?", lesson_number=2)

        mock_vector_store.search.assert_called_once_with(
            query="What is RAG?",
            course_name=None,
            lesson_number=2
        )

    def test_execute_with_both_filters(self, mock_vector_store, sample_search_results):
        """Test execute with both course and lesson filters."""
        mock_vector_store.search.return_value = sample_search_results

        tool = CourseSearchTool(mock_vector_store)
        tool.execute(query="What is RAG?", course_name="MCP", lesson_number=1)

        mock_vector_store.search.assert_called_once_with(
            query="What is RAG?",
            course_name="MCP",
            lesson_number=1
        )

    def test_execute_handles_empty_results(self, mock_vector_store):
        """Test that execute returns appropriate message for empty results."""
        mock_vector_store.search.return_value = SearchResults(
            documents=[],
            metadata=[],
            distances=[]
        )

        tool = CourseSearchTool(mock_vector_store)
        result = tool.execute(query="nonexistent topic")

        assert "No relevant content found" in result

    def test_execute_handles_empty_results_with_filters(self, mock_vector_store):
        """Test empty results message includes filter info."""
        mock_vector_store.search.return_value = SearchResults(
            documents=[],
            metadata=[],
            distances=[]
        )

        tool = CourseSearchTool(mock_vector_store)
        result = tool.execute(query="topic", course_name="MCP", lesson_number=5)

        assert "No relevant content found" in result
        assert "in course 'MCP'" in result
        assert "in lesson 5" in result

    def test_execute_handles_search_error(self, mock_vector_store):
        """Test that execute returns error message on search failure."""
        mock_vector_store.search.return_value = SearchResults(
            documents=[],
            metadata=[],
            distances=[],
            error="Database connection failed"
        )

        tool = CourseSearchTool(mock_vector_store)
        result = tool.execute(query="What is RAG?")

        assert result == "Database connection failed"

    def test_execute_stores_sources(self, mock_vector_store, sample_search_results):
        """Test that execute populates last_sources for UI."""
        mock_vector_store.search.return_value = sample_search_results
        mock_vector_store.get_lesson_link.return_value = "https://example.com/lesson"

        tool = CourseSearchTool(mock_vector_store)
        tool.execute(query="What is RAG?")

        assert len(tool.last_sources) == 2
        assert tool.last_sources[0]["text"] == "Introduction to RAG - Lesson 1"
        assert tool.last_sources[0]["url"] == "https://example.com/lesson"

    def test_execute_handles_missing_lesson_number(self, mock_vector_store):
        """Test formatting when lesson_number is None in metadata."""
        mock_vector_store.search.return_value = SearchResults(
            documents=["Course overview content"],
            metadata=[{"course_title": "Test Course", "lesson_number": None}],
            distances=[0.1]
        )

        tool = CourseSearchTool(mock_vector_store)
        result = tool.execute(query="overview")

        # Should not include "Lesson None"
        assert "[Test Course]" in result
        assert "Lesson None" not in result


class TestCourseOutlineToolExecute:
    """Test suite for CourseOutlineTool.execute() method."""

    def test_execute_returns_formatted_outline(self, mock_vector_store, sample_course_outline):
        """Test that execute returns properly formatted course outline."""
        mock_vector_store.get_course_outline.return_value = sample_course_outline

        tool = CourseOutlineTool(mock_vector_store)
        result = tool.execute(course_name="MCP")

        assert "Course: MCP: Build Rich-Context AI Apps" in result
        assert "Course Link: https://example.com/mcp-course" in result
        assert "Lesson 0: Introduction" in result
        assert "Lesson 1: Getting Started" in result
        assert "Lesson 2: Advanced Topics" in result

    def test_execute_handles_course_not_found(self, mock_vector_store):
        """Test that execute returns error for unknown course."""
        mock_vector_store.get_course_outline.return_value = None

        tool = CourseOutlineTool(mock_vector_store)
        result = tool.execute(course_name="Unknown Course")

        assert "No course found matching 'Unknown Course'" in result


class TestToolManager:
    """Test suite for ToolManager."""

    def test_register_tool(self, mock_vector_store):
        """Test tool registration."""
        manager = ToolManager()
        tool = CourseSearchTool(mock_vector_store)

        manager.register_tool(tool)

        assert "search_course_content" in manager.tools
        assert manager.tools["search_course_content"] == tool

    def test_get_tool_definitions(self, mock_vector_store):
        """Test getting tool definitions for API."""
        manager = ToolManager()
        manager.register_tool(CourseSearchTool(mock_vector_store))
        manager.register_tool(CourseOutlineTool(mock_vector_store))

        definitions = manager.get_tool_definitions()

        assert len(definitions) == 2
        names = [d["name"] for d in definitions]
        assert "search_course_content" in names
        assert "get_course_outline" in names

    def test_execute_tool(self, mock_vector_store, sample_search_results):
        """Test tool execution via manager."""
        mock_vector_store.search.return_value = sample_search_results

        manager = ToolManager()
        manager.register_tool(CourseSearchTool(mock_vector_store))

        result = manager.execute_tool("search_course_content", query="RAG")

        assert "RAG stands for" in result

    def test_execute_unknown_tool(self, mock_vector_store):
        """Test executing non-existent tool."""
        manager = ToolManager()
        manager.register_tool(CourseSearchTool(mock_vector_store))

        result = manager.execute_tool("unknown_tool", query="test")

        assert "Tool 'unknown_tool' not found" in result

    def test_get_last_sources(self, mock_vector_store, sample_search_results):
        """Test retrieving sources after search."""
        mock_vector_store.search.return_value = sample_search_results

        manager = ToolManager()
        search_tool = CourseSearchTool(mock_vector_store)
        manager.register_tool(search_tool)

        manager.execute_tool("search_course_content", query="RAG")
        sources = manager.get_last_sources()

        assert len(sources) == 2

    def test_reset_sources(self, mock_vector_store, sample_search_results):
        """Test resetting sources."""
        mock_vector_store.search.return_value = sample_search_results

        manager = ToolManager()
        search_tool = CourseSearchTool(mock_vector_store)
        manager.register_tool(search_tool)

        manager.execute_tool("search_course_content", query="RAG")
        manager.reset_sources()
        sources = manager.get_last_sources()

        assert sources == []

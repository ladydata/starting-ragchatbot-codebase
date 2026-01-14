"""Tests for VectorStore and SearchResults."""
import pytest
from unittest.mock import Mock, MagicMock, patch
import tempfile
import shutil
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vector_store import VectorStore, SearchResults
from models import Course, Lesson, CourseChunk


class TestSearchResults:
    """Test suite for SearchResults dataclass."""

    def test_from_chroma_parses_results(self):
        """Test parsing ChromaDB query results."""
        chroma_results = {
            'documents': [['doc1', 'doc2']],
            'metadatas': [[{'course_title': 'Course A'}, {'course_title': 'Course B'}]],
            'distances': [[0.1, 0.2]]
        }

        results = SearchResults.from_chroma(chroma_results)

        assert results.documents == ['doc1', 'doc2']
        assert len(results.metadata) == 2
        assert results.distances == [0.1, 0.2]
        assert results.error is None

    def test_from_chroma_handles_empty_results(self):
        """Test parsing empty ChromaDB results."""
        chroma_results = {
            'documents': [[]],
            'metadatas': [[]],
            'distances': [[]]
        }

        results = SearchResults.from_chroma(chroma_results)

        assert results.documents == []
        assert results.metadata == []
        assert results.is_empty()

    def test_empty_creates_error_result(self):
        """Test creating empty results with error message."""
        results = SearchResults.empty("Connection failed")

        assert results.documents == []
        assert results.error == "Connection failed"
        assert results.is_empty()

    def test_is_empty_returns_true_for_no_documents(self):
        """Test is_empty returns True when no documents."""
        results = SearchResults(documents=[], metadata=[], distances=[])
        assert results.is_empty()

    def test_is_empty_returns_false_with_documents(self):
        """Test is_empty returns False when documents exist."""
        results = SearchResults(
            documents=['content'],
            metadata=[{'title': 'Test'}],
            distances=[0.1]
        )
        assert not results.is_empty()


class TestVectorStoreBuildFilter:
    """Test suite for VectorStore._build_filter method."""

    @pytest.fixture
    def vector_store(self):
        """Create VectorStore with mocked ChromaDB."""
        with patch('vector_store.chromadb.PersistentClient'), \
             patch('vector_store.chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction'):
            store = VectorStore(
                chroma_path="/tmp/test_chroma",
                embedding_model="all-MiniLM-L6-v2"
            )
            return store

    def test_build_filter_returns_none_when_no_filters(self, vector_store):
        """Test no filter when neither course nor lesson specified."""
        result = vector_store._build_filter(None, None)
        assert result is None

    def test_build_filter_with_course_only(self, vector_store):
        """Test filter with course title only."""
        result = vector_store._build_filter("Test Course", None)
        assert result == {"course_title": "Test Course"}

    def test_build_filter_with_lesson_only(self, vector_store):
        """Test filter with lesson number only."""
        result = vector_store._build_filter(None, 5)
        assert result == {"lesson_number": 5}

    def test_build_filter_with_both(self, vector_store):
        """Test filter with both course and lesson."""
        result = vector_store._build_filter("Test Course", 3)

        assert result == {
            "$and": [
                {"course_title": "Test Course"},
                {"lesson_number": 3}
            ]
        }

    def test_build_filter_lesson_zero_is_valid(self, vector_store):
        """Test that lesson 0 is treated as valid filter."""
        result = vector_store._build_filter(None, 0)
        assert result == {"lesson_number": 0}


class TestVectorStoreSearch:
    """Test suite for VectorStore.search method."""

    @pytest.fixture
    def vector_store_with_mocks(self):
        """Create VectorStore with mocked collections."""
        with patch('vector_store.chromadb.PersistentClient') as mock_client, \
             patch('vector_store.chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction'):

            store = VectorStore(
                chroma_path="/tmp/test_chroma",
                embedding_model="all-MiniLM-L6-v2"
            )

            # Mock course_content collection
            store.course_content = Mock()
            store.course_content.query.return_value = {
                'documents': [['RAG content here']],
                'metadatas': [[{'course_title': 'RAG Course', 'lesson_number': 1}]],
                'distances': [[0.15]]
            }

            # Mock course_catalog for name resolution
            store.course_catalog = Mock()
            store.course_catalog.query.return_value = {
                'documents': [['RAG Course']],
                'metadatas': [[{'title': 'RAG Course'}]],
                'distances': [[0.1]]
            }

            return store

    def test_search_returns_results(self, vector_store_with_mocks):
        """Test basic search returns SearchResults."""
        results = vector_store_with_mocks.search(query="What is RAG?")

        assert not results.is_empty()
        assert "RAG content" in results.documents[0]
        assert results.metadata[0]['course_title'] == 'RAG Course'

    def test_search_with_course_filter_resolves_name(self, vector_store_with_mocks):
        """Test search with course name triggers resolution."""
        vector_store_with_mocks.search(query="test", course_name="RAG")

        # Should have queried catalog to resolve name
        vector_store_with_mocks.course_catalog.query.assert_called_once()

    def test_search_with_unresolved_course_returns_error(self, vector_store_with_mocks):
        """Test search returns error when course not found."""
        vector_store_with_mocks.course_catalog.query.return_value = {
            'documents': [[]],
            'metadatas': [[]],
            'distances': [[]]
        }

        results = vector_store_with_mocks.search(query="test", course_name="Unknown")

        assert results.error is not None
        assert "No course found" in results.error

    def test_search_uses_limit_parameter(self, vector_store_with_mocks):
        """Test search respects limit parameter."""
        vector_store_with_mocks.search(query="test", limit=10)

        call_args = vector_store_with_mocks.course_content.query.call_args
        assert call_args[1]['n_results'] == 10

    def test_search_uses_default_max_results(self, vector_store_with_mocks):
        """Test search uses configured max_results as default."""
        vector_store_with_mocks.max_results = 5
        vector_store_with_mocks.search(query="test")

        call_args = vector_store_with_mocks.course_content.query.call_args
        assert call_args[1]['n_results'] == 5

    def test_search_handles_exception(self, vector_store_with_mocks):
        """Test search handles database exceptions gracefully."""
        vector_store_with_mocks.course_content.query.side_effect = Exception("DB error")

        results = vector_store_with_mocks.search(query="test")

        assert results.error is not None
        assert "Search error" in results.error


class TestVectorStoreCourseMetadata:
    """Test suite for course metadata operations."""

    @pytest.fixture
    def vector_store_with_mocks(self):
        """Create VectorStore with mocked collections."""
        with patch('vector_store.chromadb.PersistentClient'), \
             patch('vector_store.chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction'):

            store = VectorStore(
                chroma_path="/tmp/test_chroma",
                embedding_model="all-MiniLM-L6-v2"
            )
            store.course_catalog = Mock()
            store.course_content = Mock()
            return store

    @pytest.fixture
    def sample_course(self):
        """Create a sample Course for testing."""
        return Course(
            title="Test Course",
            instructor="John Doe",
            course_link="https://example.com/course",
            lessons=[
                Lesson(lesson_number=0, title="Introduction", lesson_link="https://example.com/l0"),
                Lesson(lesson_number=1, title="Basics", lesson_link="https://example.com/l1"),
            ]
        )

    def test_add_course_metadata(self, vector_store_with_mocks, sample_course):
        """Test adding course metadata to catalog."""
        vector_store_with_mocks.add_course_metadata(sample_course)

        vector_store_with_mocks.course_catalog.add.assert_called_once()
        call_args = vector_store_with_mocks.course_catalog.add.call_args

        assert call_args[1]['documents'] == ["Test Course"]
        assert call_args[1]['ids'] == ["Test Course"]

        metadata = call_args[1]['metadatas'][0]
        assert metadata['title'] == "Test Course"
        assert metadata['instructor'] == "John Doe"
        assert metadata['lesson_count'] == 2
        assert 'lessons_json' in metadata

    def test_get_course_link(self, vector_store_with_mocks):
        """Test retrieving course link."""
        vector_store_with_mocks.course_catalog.get.return_value = {
            'metadatas': [{'course_link': 'https://example.com/course'}]
        }

        link = vector_store_with_mocks.get_course_link("Test Course")

        assert link == 'https://example.com/course'
        vector_store_with_mocks.course_catalog.get.assert_called_with(ids=["Test Course"])

    def test_get_course_link_not_found(self, vector_store_with_mocks):
        """Test course link returns None when not found."""
        vector_store_with_mocks.course_catalog.get.return_value = {'metadatas': []}

        link = vector_store_with_mocks.get_course_link("Unknown Course")

        assert link is None

    def test_get_lesson_link(self, vector_store_with_mocks):
        """Test retrieving lesson link."""
        import json
        lessons = [
            {"lesson_number": 0, "lesson_title": "Intro", "lesson_link": "https://example.com/l0"},
            {"lesson_number": 1, "lesson_title": "Basics", "lesson_link": "https://example.com/l1"}
        ]
        vector_store_with_mocks.course_catalog.get.return_value = {
            'metadatas': [{'lessons_json': json.dumps(lessons)}]
        }

        link = vector_store_with_mocks.get_lesson_link("Test Course", 1)

        assert link == "https://example.com/l1"

    def test_get_lesson_link_not_found(self, vector_store_with_mocks):
        """Test lesson link returns None for non-existent lesson."""
        import json
        lessons = [{"lesson_number": 0, "lesson_title": "Intro", "lesson_link": "https://example.com/l0"}]
        vector_store_with_mocks.course_catalog.get.return_value = {
            'metadatas': [{'lessons_json': json.dumps(lessons)}]
        }

        link = vector_store_with_mocks.get_lesson_link("Test Course", 99)

        assert link is None


class TestVectorStoreCourseOutline:
    """Test suite for get_course_outline method."""

    @pytest.fixture
    def vector_store_with_mocks(self):
        """Create VectorStore with mocked collections."""
        with patch('vector_store.chromadb.PersistentClient'), \
             patch('vector_store.chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction'):

            store = VectorStore(
                chroma_path="/tmp/test_chroma",
                embedding_model="all-MiniLM-L6-v2"
            )
            store.course_catalog = Mock()
            return store

    def test_get_course_outline_returns_full_outline(self, vector_store_with_mocks):
        """Test getting complete course outline."""
        import json
        lessons = [
            {"lesson_number": 0, "lesson_title": "Introduction", "lesson_link": "https://ex.com/0"},
            {"lesson_number": 1, "lesson_title": "Getting Started", "lesson_link": "https://ex.com/1"}
        ]

        # Mock name resolution
        vector_store_with_mocks.course_catalog.query.return_value = {
            'documents': [['MCP Course']],
            'metadatas': [[{'title': 'MCP Course'}]],
            'distances': [[0.1]]
        }

        # Mock course retrieval
        vector_store_with_mocks.course_catalog.get.return_value = {
            'metadatas': [{
                'title': 'MCP Course',
                'course_link': 'https://example.com/mcp',
                'lessons_json': json.dumps(lessons)
            }]
        }

        outline = vector_store_with_mocks.get_course_outline("MCP")

        assert outline is not None
        assert outline['title'] == 'MCP Course'
        assert outline['course_link'] == 'https://example.com/mcp'
        assert len(outline['lessons']) == 2
        assert outline['lessons'][0]['lesson_title'] == 'Introduction'

    def test_get_course_outline_not_found(self, vector_store_with_mocks):
        """Test get_course_outline returns None for unknown course."""
        vector_store_with_mocks.course_catalog.query.return_value = {
            'documents': [[]],
            'metadatas': [[]],
            'distances': [[]]
        }

        outline = vector_store_with_mocks.get_course_outline("Unknown")

        assert outline is None

    def test_get_course_outline_uses_vector_search(self, vector_store_with_mocks):
        """Test that partial course names work via vector search."""
        import json
        vector_store_with_mocks.course_catalog.query.return_value = {
            'documents': [['MCP: Build Rich-Context AI Apps']],
            'metadatas': [[{'title': 'MCP: Build Rich-Context AI Apps'}]],
            'distances': [[0.05]]
        }
        vector_store_with_mocks.course_catalog.get.return_value = {
            'metadatas': [{
                'title': 'MCP: Build Rich-Context AI Apps',
                'course_link': 'https://example.com',
                'lessons_json': json.dumps([])
            }]
        }

        outline = vector_store_with_mocks.get_course_outline("MCP")

        # Verify vector search was used
        vector_store_with_mocks.course_catalog.query.assert_called_once_with(
            query_texts=["MCP"],
            n_results=1
        )


class TestVectorStoreCourseContent:
    """Test suite for course content operations."""

    @pytest.fixture
    def vector_store_with_mocks(self):
        """Create VectorStore with mocked collections."""
        with patch('vector_store.chromadb.PersistentClient'), \
             patch('vector_store.chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction'):

            store = VectorStore(
                chroma_path="/tmp/test_chroma",
                embedding_model="all-MiniLM-L6-v2"
            )
            store.course_content = Mock()
            return store

    def test_add_course_content(self, vector_store_with_mocks):
        """Test adding course content chunks."""
        chunks = [
            CourseChunk(course_title="Test", lesson_number=0, chunk_index=0, content="First chunk"),
            CourseChunk(course_title="Test", lesson_number=0, chunk_index=1, content="Second chunk")
        ]

        vector_store_with_mocks.add_course_content(chunks)

        vector_store_with_mocks.course_content.add.assert_called_once()
        call_args = vector_store_with_mocks.course_content.add.call_args

        assert call_args[1]['documents'] == ["First chunk", "Second chunk"]
        assert len(call_args[1]['ids']) == 2

    def test_add_course_content_empty_list(self, vector_store_with_mocks):
        """Test adding empty chunk list does nothing."""
        vector_store_with_mocks.add_course_content([])

        vector_store_with_mocks.course_content.add.assert_not_called()

    def test_chunk_ids_are_unique(self, vector_store_with_mocks):
        """Test that chunk IDs are unique."""
        chunks = [
            CourseChunk(course_title="Course A", lesson_number=0, chunk_index=0, content="A"),
            CourseChunk(course_title="Course A", lesson_number=0, chunk_index=1, content="B"),
            CourseChunk(course_title="Course B", lesson_number=1, chunk_index=0, content="C")
        ]

        vector_store_with_mocks.add_course_content(chunks)

        call_args = vector_store_with_mocks.course_content.add.call_args
        ids = call_args[1]['ids']

        # All IDs should be unique
        assert len(ids) == len(set(ids))


class TestVectorStoreUtilities:
    """Test suite for utility methods."""

    @pytest.fixture
    def vector_store_with_mocks(self):
        """Create VectorStore with mocked collections."""
        with patch('vector_store.chromadb.PersistentClient'), \
             patch('vector_store.chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction'):

            store = VectorStore(
                chroma_path="/tmp/test_chroma",
                embedding_model="all-MiniLM-L6-v2"
            )
            store.course_catalog = Mock()
            return store

    def test_get_existing_course_titles(self, vector_store_with_mocks):
        """Test getting all course titles."""
        vector_store_with_mocks.course_catalog.get.return_value = {
            'ids': ['Course A', 'Course B', 'Course C']
        }

        titles = vector_store_with_mocks.get_existing_course_titles()

        assert titles == ['Course A', 'Course B', 'Course C']

    def test_get_course_count(self, vector_store_with_mocks):
        """Test getting course count."""
        vector_store_with_mocks.course_catalog.get.return_value = {
            'ids': ['A', 'B', 'C', 'D']
        }

        count = vector_store_with_mocks.get_course_count()

        assert count == 4

    def test_get_all_courses_metadata(self, vector_store_with_mocks):
        """Test getting all courses metadata with parsed lessons."""
        import json
        vector_store_with_mocks.course_catalog.get.return_value = {
            'metadatas': [
                {
                    'title': 'Course A',
                    'instructor': 'Teacher A',
                    'lessons_json': json.dumps([{'lesson_number': 0, 'lesson_title': 'Intro'}])
                },
                {
                    'title': 'Course B',
                    'instructor': 'Teacher B',
                    'lessons_json': json.dumps([])
                }
            ]
        }

        metadata = vector_store_with_mocks.get_all_courses_metadata()

        assert len(metadata) == 2
        assert metadata[0]['title'] == 'Course A'
        assert 'lessons' in metadata[0]  # Parsed from JSON
        assert 'lessons_json' not in metadata[0]  # JSON string removed
        assert len(metadata[0]['lessons']) == 1

"""Tests for AIGenerator tool calling behavior."""
import pytest
from unittest.mock import Mock, MagicMock, patch
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_generator import AIGenerator
from search_tools import ToolManager, CourseSearchTool


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


class TestAIGeneratorToolCalling:
    """Test suite for AIGenerator tool calling behavior."""

    @pytest.fixture
    def ai_generator(self):
        """Create AIGenerator with mocked client."""
        with patch('ai_generator.anthropic.Anthropic') as mock_anthropic:
            generator = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")
            return generator

    @pytest.fixture
    def mock_tool_manager(self, mock_vector_store, sample_search_results):
        """Create a mock tool manager with search tool."""
        mock_vector_store.search.return_value = sample_search_results

        manager = ToolManager()
        manager.register_tool(CourseSearchTool(mock_vector_store))
        return manager

    def test_generate_response_without_tools(self, ai_generator):
        """Test direct response without tool usage."""
        # Mock a direct response (no tool use)
        ai_generator.client.messages.create.return_value = MockResponse(
            content=[MockContentBlock("text", text="This is a direct answer.")],
            stop_reason="end_turn"
        )

        result = ai_generator.generate_response(
            query="What is Python?",
            tools=None,
            tool_manager=None
        )

        assert result == "This is a direct answer."

    def test_generate_response_calls_tool_when_needed(self, ai_generator, mock_tool_manager):
        """Test that AI correctly triggers tool use for course questions."""
        tools = mock_tool_manager.get_tool_definitions()

        # First call returns tool_use, second call returns final response
        ai_generator.client.messages.create.side_effect = [
            MockResponse(
                content=[
                    MockContentBlock(
                        "tool_use",
                        tool_name="search_course_content",
                        tool_input={"query": "RAG explanation"},
                        tool_id="tool_123"
                    )
                ],
                stop_reason="tool_use"
            ),
            MockResponse(
                content=[MockContentBlock("text", text="RAG is Retrieval-Augmented Generation.")],
                stop_reason="end_turn"
            )
        ]

        result = ai_generator.generate_response(
            query="What is RAG?",
            tools=tools,
            tool_manager=mock_tool_manager
        )

        # Verify tool was executed
        assert ai_generator.client.messages.create.call_count == 2
        assert "RAG is Retrieval-Augmented Generation" in result

    def test_tool_execution_passes_correct_parameters(self, ai_generator, mock_tool_manager):
        """Test that tool parameters from Claude are correctly passed."""
        tools = mock_tool_manager.get_tool_definitions()

        ai_generator.client.messages.create.side_effect = [
            MockResponse(
                content=[
                    MockContentBlock(
                        "tool_use",
                        tool_name="search_course_content",
                        tool_input={"query": "MCP protocol", "course_name": "MCP Course"},
                        tool_id="tool_456"
                    )
                ],
                stop_reason="tool_use"
            ),
            MockResponse(
                content=[MockContentBlock("text", text="The MCP protocol...")],
                stop_reason="end_turn"
            )
        ]

        # Spy on tool execution
        original_execute = mock_tool_manager.execute_tool
        mock_tool_manager.execute_tool = Mock(side_effect=original_execute)

        ai_generator.generate_response(
            query="Tell me about MCP",
            tools=tools,
            tool_manager=mock_tool_manager
        )

        # Verify tool was called with correct parameters
        mock_tool_manager.execute_tool.assert_called_once_with(
            "search_course_content",
            query="MCP protocol",
            course_name="MCP Course"
        )

    def test_tool_results_included_in_followup(self, ai_generator, mock_tool_manager):
        """Test that tool results are included in the follow-up API call."""
        tools = mock_tool_manager.get_tool_definitions()

        ai_generator.client.messages.create.side_effect = [
            MockResponse(
                content=[
                    MockContentBlock(
                        "tool_use",
                        tool_name="search_course_content",
                        tool_input={"query": "RAG"},
                        tool_id="tool_789"
                    )
                ],
                stop_reason="tool_use"
            ),
            MockResponse(
                content=[MockContentBlock("text", text="Final response")],
                stop_reason="end_turn"
            )
        ]

        ai_generator.generate_response(
            query="What is RAG?",
            tools=tools,
            tool_manager=mock_tool_manager
        )

        # Check second API call includes tool results
        second_call_args = ai_generator.client.messages.create.call_args_list[1]
        messages = second_call_args[1]["messages"]

        # Should have: user message, assistant tool_use, user tool_result
        assert len(messages) == 3
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"
        assert messages[2]["role"] == "user"
        assert messages[2]["content"][0]["type"] == "tool_result"

    def test_no_tool_use_for_general_questions(self, ai_generator, mock_tool_manager):
        """Test that general questions don't trigger tool use."""
        tools = mock_tool_manager.get_tool_definitions()

        # Claude decides not to use tools
        ai_generator.client.messages.create.return_value = MockResponse(
            content=[MockContentBlock("text", text="Python is a programming language.")],
            stop_reason="end_turn"
        )

        result = ai_generator.generate_response(
            query="What is Python?",
            tools=tools,
            tool_manager=mock_tool_manager
        )

        # Only one API call, no tool execution
        assert ai_generator.client.messages.create.call_count == 1
        assert "Python is a programming language" in result

    def test_conversation_history_included(self, ai_generator):
        """Test that conversation history is included in system prompt."""
        ai_generator.client.messages.create.return_value = MockResponse(
            content=[MockContentBlock("text", text="Based on our discussion...")],
            stop_reason="end_turn"
        )

        history = "User: Hello\nAssistant: Hi there!"
        ai_generator.generate_response(
            query="Continue",
            conversation_history=history
        )

        call_args = ai_generator.client.messages.create.call_args
        system_content = call_args[1]["system"]

        assert "Previous conversation:" in system_content
        assert history in system_content

    def test_tools_passed_to_api(self, ai_generator, mock_tool_manager):
        """Test that tool definitions are correctly passed to the API."""
        tools = mock_tool_manager.get_tool_definitions()

        ai_generator.client.messages.create.return_value = MockResponse(
            content=[MockContentBlock("text", text="Response")],
            stop_reason="end_turn"
        )

        ai_generator.generate_response(
            query="Question",
            tools=tools,
            tool_manager=mock_tool_manager
        )

        call_args = ai_generator.client.messages.create.call_args
        assert "tools" in call_args[1]
        assert call_args[1]["tools"] == tools
        assert call_args[1]["tool_choice"] == {"type": "auto"}

    def test_second_call_has_tools_for_potential_followup(self, ai_generator, mock_tool_manager):
        """Test that follow-up call after first tool use still includes tools."""
        tools = mock_tool_manager.get_tool_definitions()

        ai_generator.client.messages.create.side_effect = [
            MockResponse(
                content=[
                    MockContentBlock(
                        "tool_use",
                        tool_name="search_course_content",
                        tool_input={"query": "test"},
                        tool_id="tool_abc"
                    )
                ],
                stop_reason="tool_use"
            ),
            MockResponse(
                content=[MockContentBlock("text", text="Final")],
                stop_reason="end_turn"
            )
        ]

        ai_generator.generate_response(
            query="Test",
            tools=tools,
            tool_manager=mock_tool_manager
        )

        # Second call SHOULD have tools (for potential second tool call)
        second_call_args = ai_generator.client.messages.create.call_args_list[1]
        assert "tools" in second_call_args[1]
        assert second_call_args[1]["tools"] == tools


class TestSequentialToolCalling:
    """Test suite for sequential tool calling behavior."""

    @pytest.fixture
    def ai_generator(self):
        """Create AIGenerator with mocked client."""
        with patch('ai_generator.anthropic.Anthropic') as mock_anthropic:
            generator = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")
            return generator

    @pytest.fixture
    def mock_tool_manager(self):
        """Create a mock tool manager."""
        manager = Mock()
        manager.execute_tool.return_value = "Tool result"
        manager.get_tool_definitions.return_value = [{"name": "test_tool"}]
        return manager

    def test_single_tool_call_two_api_calls(self, ai_generator, mock_tool_manager):
        """Single tool call followed by text response makes 2 API calls."""
        tools = [{"name": "search_course_content"}]

        ai_generator.client.messages.create.side_effect = [
            MockResponse(
                content=[MockContentBlock("tool_use", tool_name="search", tool_input={"q": "test"}, tool_id="t1")],
                stop_reason="tool_use"
            ),
            MockResponse(
                content=[MockContentBlock("text", text="Answer")],
                stop_reason="end_turn"
            )
        ]

        result = ai_generator.generate_response(query="Q", tools=tools, tool_manager=mock_tool_manager)

        assert ai_generator.client.messages.create.call_count == 2
        assert result == "Answer"

    def test_two_sequential_tool_calls(self, ai_generator, mock_tool_manager):
        """Two tool calls before final response makes 3 API calls."""
        tools = [{"name": "search_course_content"}]

        ai_generator.client.messages.create.side_effect = [
            MockResponse(
                content=[MockContentBlock("tool_use", tool_name="search", tool_input={"q": "first"}, tool_id="t1")],
                stop_reason="tool_use"
            ),
            MockResponse(
                content=[MockContentBlock("tool_use", tool_name="search", tool_input={"q": "second"}, tool_id="t2")],
                stop_reason="tool_use"
            ),
            MockResponse(
                content=[MockContentBlock("text", text="Combined answer")],
                stop_reason="end_turn"
            )
        ]

        result = ai_generator.generate_response(query="Q", tools=tools, tool_manager=mock_tool_manager)

        assert ai_generator.client.messages.create.call_count == 3
        assert mock_tool_manager.execute_tool.call_count == 2
        assert result == "Combined answer"

    def test_max_rounds_forces_final_call_without_tools(self, ai_generator, mock_tool_manager):
        """After MAX_TOOL_ROUNDS, final call has no tools."""
        tools = [{"name": "search_course_content"}]

        ai_generator.client.messages.create.side_effect = [
            MockResponse(
                content=[MockContentBlock("tool_use", tool_name="search", tool_input={"q": "1"}, tool_id="t1")],
                stop_reason="tool_use"
            ),
            MockResponse(
                content=[MockContentBlock("tool_use", tool_name="search", tool_input={"q": "2"}, tool_id="t2")],
                stop_reason="tool_use"
            ),
            MockResponse(
                content=[MockContentBlock("text", text="Best effort")],
                stop_reason="end_turn"
            )
        ]

        ai_generator.generate_response(query="Q", tools=tools, tool_manager=mock_tool_manager)

        # Third call (after 2 tool rounds) should NOT have tools
        third_call = ai_generator.client.messages.create.call_args_list[2]
        assert "tools" not in third_call[1]

    def test_no_tool_use_returns_immediately(self, ai_generator):
        """Direct response without tool use makes only 1 API call."""
        ai_generator.client.messages.create.return_value = MockResponse(
            content=[MockContentBlock("text", text="Direct answer")],
            stop_reason="end_turn"
        )

        result = ai_generator.generate_response(query="Q", tools=[{"name": "tool"}], tool_manager=Mock())

        assert ai_generator.client.messages.create.call_count == 1
        assert result == "Direct answer"

    def test_tool_error_continues_gracefully(self, ai_generator, mock_tool_manager):
        """Tool exception is caught and returned as error string."""
        tools = [{"name": "search"}]
        mock_tool_manager.execute_tool.side_effect = Exception("DB connection failed")

        ai_generator.client.messages.create.side_effect = [
            MockResponse(
                content=[MockContentBlock("tool_use", tool_name="search", tool_input={"q": "test"}, tool_id="t1")],
                stop_reason="tool_use"
            ),
            MockResponse(
                content=[MockContentBlock("text", text="Sorry, I encountered an error.")],
                stop_reason="end_turn"
            )
        ]

        result = ai_generator.generate_response(query="Q", tools=tools, tool_manager=mock_tool_manager)

        # Should not raise, should return graceful response
        assert "Sorry" in result

        # Verify error was passed to Claude
        second_call = ai_generator.client.messages.create.call_args_list[1]
        tool_result_msg = second_call[1]["messages"][2]
        assert "Tool error" in tool_result_msg["content"][0]["content"]

    def test_messages_accumulate_across_rounds(self, ai_generator, mock_tool_manager):
        """Message history grows correctly across tool rounds."""
        tools = [{"name": "search"}]

        ai_generator.client.messages.create.side_effect = [
            MockResponse(
                content=[MockContentBlock("tool_use", tool_name="search", tool_input={"q": "1"}, tool_id="t1")],
                stop_reason="tool_use"
            ),
            MockResponse(
                content=[MockContentBlock("tool_use", tool_name="search", tool_input={"q": "2"}, tool_id="t2")],
                stop_reason="tool_use"
            ),
            MockResponse(
                content=[MockContentBlock("text", text="Final")],
                stop_reason="end_turn"
            )
        ]

        ai_generator.generate_response(query="Q", tools=tools, tool_manager=mock_tool_manager)

        # Final call should have accumulated messages:
        # user query, assistant tool_use 1, user tool_result 1, assistant tool_use 2, user tool_result 2
        final_call = ai_generator.client.messages.create.call_args_list[2]
        messages = final_call[1]["messages"]
        assert len(messages) == 5
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"
        assert messages[2]["role"] == "user"
        assert messages[3]["role"] == "assistant"
        assert messages[4]["role"] == "user"


class TestAIGeneratorSystemPrompt:
    """Test suite for AIGenerator system prompt configuration."""

    def test_system_prompt_mentions_both_tools(self):
        """Verify system prompt guides usage of both tools."""
        prompt = AIGenerator.SYSTEM_PROMPT

        assert "search_course_content" in prompt
        assert "get_course_outline" in prompt

    def test_system_prompt_has_tool_selection_guidance(self):
        """Verify system prompt guides when to use which tool."""
        prompt = AIGenerator.SYSTEM_PROMPT

        # Should guide outline tool for structure questions
        assert "outline" in prompt.lower() or "structure" in prompt.lower()
        # Should guide search tool for content questions
        assert "content" in prompt.lower() or "search" in prompt.lower()

    def test_system_prompt_allows_multi_step_reasoning(self):
        """Verify system prompt allows multiple tool calls."""
        prompt = AIGenerator.SYSTEM_PROMPT

        # Should mention multi-step or sequential tool usage
        assert "2 tool calls" in prompt or "multiple tools" in prompt.lower()
        # Should NOT have the old "one tool per query" restriction
        assert "one tool use per query maximum" not in prompt.lower()

    def test_max_tool_rounds_constant(self):
        """Verify MAX_TOOL_ROUNDS is configured."""
        assert hasattr(AIGenerator, 'MAX_TOOL_ROUNDS')
        assert AIGenerator.MAX_TOOL_ROUNDS == 2

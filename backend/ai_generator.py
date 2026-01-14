import anthropic
from typing import List, Optional, Dict, Any

class AIGenerator:
    """Handles interactions with Anthropic's Claude API for generating responses"""
    
    # Maximum sequential tool rounds per query
    MAX_TOOL_ROUNDS = 2

    # Static system prompt to avoid rebuilding on each call
    SYSTEM_PROMPT = """You are an AI assistant specialized in course materials and educational content with access to tools for course information.

Available Tools:
1. **search_course_content**: Search course materials for specific content or detailed information
2. **get_course_outline**: Get course structure including title, link, and all lessons with their numbers and titles

Tool Selection:
- **Outline questions** (syllabus, structure, what lessons, course overview): Use get_course_outline
- **Content questions** (specific topics, details, explanations): Use search_course_content
- **General knowledge**: Answer without tools

Multi-Step Reasoning:
- You may use up to 2 tool calls sequentially when needed
- Use multiple tools when:
  * Comparing information from different courses or lessons
  * Need both outline AND content information
  * First search needs refinement with different terms
- Synthesize all tool results into a single cohesive response

Response Protocol:
- Provide direct answers without meta-commentary
- Do not mention "based on the search results" or explain the search process

For outline responses, include:
- Course title and link
- Complete lesson list with lesson numbers and titles

All responses must be:
1. Brief, concise and focused
2. Educational with instructional value
3. Clear with accessible language
4. Example-supported when helpful
"""
    
    def __init__(self, api_key: str, model: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        
        # Pre-build base API parameters
        self.base_params = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": 800
        }
    
    def generate_response(self, query: str,
                         conversation_history: Optional[str] = None,
                         tools: Optional[List] = None,
                         tool_manager=None) -> str:
        """
        Generate AI response with optional tool usage and conversation context.
        Supports up to MAX_TOOL_ROUNDS sequential tool calls.

        Args:
            query: The user's question or request
            conversation_history: Previous messages for context
            tools: Available tools the AI can use
            tool_manager: Manager to execute tools

        Returns:
            Generated response as string
        """
        # Build system content
        system_content = (
            f"{self.SYSTEM_PROMPT}\n\nPrevious conversation:\n{conversation_history}"
            if conversation_history
            else self.SYSTEM_PROMPT
        )

        # Initialize messages
        messages = [{"role": "user", "content": query}]
        round_count = 0

        # Main loop - continue while tool calls needed and under limit
        while round_count < self.MAX_TOOL_ROUNDS:
            # Build API params WITH tools
            api_params = {
                **self.base_params,
                "messages": messages,
                "system": system_content
            }
            if tools:
                api_params["tools"] = tools
                api_params["tool_choice"] = {"type": "auto"}

            # Make API call
            response = self.client.messages.create(**api_params)

            # Check termination: no tool use requested
            if response.stop_reason != "tool_use":
                return response.content[0].text

            # Check termination: no tool manager
            if tool_manager is None:
                return response.content[0].text

            # Execute tools
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    try:
                        result = tool_manager.execute_tool(block.name, **block.input)
                    except Exception as e:
                        result = f"Tool error: {str(e)}"
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })

            # Update messages for next round
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})
            round_count += 1

        # Max rounds reached - final call WITHOUT tools to force text response
        final_params = {
            **self.base_params,
            "messages": messages,
            "system": system_content
        }
        final_response = self.client.messages.create(**final_params)
        return final_response.content[0].text
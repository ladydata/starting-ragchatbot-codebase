# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

**Always use `uv` for package management and running the server. Never use `pip` directly.**

```bash
# Install dependencies
uv sync

# Run the server (from project root)
cd backend && uv run uvicorn app:app --reload --port 8000

# Or use the shell script
./run.sh
```

The app runs at http://localhost:8000 with API docs at http://localhost:8000/docs.

## Architecture

This is a RAG (Retrieval-Augmented Generation) chatbot with a FastAPI backend and vanilla JS frontend.

### Query Flow

1. **Frontend** (`frontend/script.js`) sends POST to `/api/query` with `{query, session_id}`
2. **FastAPI** (`backend/app.py`) routes to `RAGSystem.query()`
3. **RAGSystem** (`backend/rag_system.py`) orchestrates:
   - Gets conversation history from `SessionManager`
   - Calls `AIGenerator.generate_response()` with the `search_course_content` tool
4. **AIGenerator** (`backend/ai_generator.py`) makes Claude API call:
   - If Claude decides to search: executes `CourseSearchTool` via `ToolManager`
   - Makes second API call with search results to get final answer
5. **CourseSearchTool** (`backend/search_tools.py`) calls `VectorStore.search()`
6. **VectorStore** (`backend/vector_store.py`) queries ChromaDB with semantic search
7. Response + sources returned to frontend

### Key Components

| File | Purpose |
|------|---------|
| `backend/rag_system.py` | Main orchestrator - coordinates all components |
| `backend/ai_generator.py` | Claude API interaction with tool use support |
| `backend/vector_store.py` | ChromaDB wrapper with two collections: `course_catalog` (metadata) and `course_content` (chunks) |
| `backend/document_processor.py` | Parses course documents, chunks text (800 chars, 100 overlap) |
| `backend/search_tools.py` | Tool definitions for Claude's tool use feature |
| `backend/session_manager.py` | In-memory conversation history per session |
| `backend/config.py` | Configuration dataclass (model, chunk size, paths) |
| `backend/models.py` | Pydantic models: Course, Lesson, CourseChunk |

### Document Format

Course documents in `docs/` follow this structure:
```
Course Title: [title]
Course Link: [url]
Course Instructor: [instructor]

Lesson 0: [lesson title]
Lesson Link: [url]
[content...]
```

### Configuration

Key settings in `backend/config.py`:
- `ANTHROPIC_MODEL`: claude-sonnet-4-20250514
- `EMBEDDING_MODEL`: all-MiniLM-L6-v2
- `CHUNK_SIZE`: 800 characters
- `CHUNK_OVERLAP`: 100 characters
- `MAX_RESULTS`: 5 search results
- `CHROMA_PATH`: ./chroma_db (persistent storage)

### Environment

Requires `.env` file with `ANTHROPIC_API_KEY`.

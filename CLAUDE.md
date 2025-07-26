# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Environment Setup

```bash
# Install package in development mode with all dependencies
pip install -e ".[dev]"
```

### Testing

```bash
# Run all tests
pytest

# Run tests with verbose output
pytest -v

# Run specific test file
pytest tests/unit/test_api_client.py

# Run specific test method
pytest tests/unit/test_api_client.py::TestRaindropClient::test_delete_bookmark_success

# Run tests with coverage
pytest --cov=raindrop_cleanup

# Run only unit tests or integration tests
pytest tests/unit/
pytest tests/integration/
```

### Code Quality

```bash
# Format code with Black
black raindrop_cleanup/ tests/

# Lint with ruff
ruff check raindrop_cleanup/ tests/

# Type checking with mypy
mypy raindrop_cleanup/

# Run all quality checks together
black raindrop_cleanup/ tests/ && ruff check raindrop_cleanup/ tests/ && mypy raindrop_cleanup/
```

### CLI Usage

```bash
# Run the CLI (requires API keys)
raindrop-cleanup

# Test CLI without making changes
raindrop-cleanup --dry-run

# List collections
raindrop-cleanup --list-collections

# Use text mode interface
raindrop-cleanup --text-mode

# Enable debug logging for Claude AI analysis
raindrop-cleanup --debug

# Use environment variable to enable debug permanently
export RAINDROP_DEBUG=1
raindrop-cleanup
```

## Architecture Overview

This is an AI-powered bookmark cleanup tool for Raindrop.io with a modular architecture designed around ADHD-friendly workflows.

### Core Architecture Pattern

The application uses a **component orchestration pattern** where `RaindropBookmarkCleaner` (in `core/processor.py`) coordinates between specialized components:

- **API Layer** (`api/raindrop_client.py`): Handles all Raindrop.io REST API interactions
- **AI Layer** (`ai/claude_analyzer.py`): Uses Claude AI to analyze bookmarks and suggest actions
- **UI Layer** (`ui/interfaces.py`): Provides both keyboard navigation and text-based interfaces
- **State Layer** (`state/manager.py`): Manages session persistence and statistics across resumable sessions
- **CLI Layer** (`cli/main.py`): Command-line interface and argument parsing

### Data Flow

1. **Collection Selection**: User selects a Raindrop collection to process
2. **Batch Processing**: Bookmarks are fetched in batches (default 8 items)
3. **AI Analysis**: Claude analyzes each batch and suggests actions (DELETE, KEEP, ARCHIVE, MOVE)
4. **User Review**: Interactive interface shows recommendations with reasoning
5. **Action execution**: Selected actions are executed via Raindrop API
6. **State Persistence**: Progress is saved after each batch for resumability

### Key Design Principles

- **Stateful Sessions**: All progress is persisted to `.raindrop_state/` directory with JSON files
- **ADHD-Friendly**: Small batches, break reminders every 25 items, conservative defaults
- **Rate Limiting**: Built-in delays for Claude API calls to prevent quota issues  
- **Dry Run Support**: All API modifications can be simulated without actual changes
- **Dual UI Modes**: Curses-based keyboard navigation with text-mode fallback

### State Management Architecture

The `StateManager` maintains:

- **Processed bookmark IDs**: Set of already-handled bookmarks to enable resumption
- **Statistics**: Counters for processed, kept, deleted, archived, moved, errors, skipped
- **Session metadata**: Collection info, current page, timing data
- **File-based persistence**: JSON files named `collection_{id}_{name}.json`

### Error Handling Strategy

- **API failures**: Continue processing other items, increment error counter
- **Missing collections**: Graceful fallback with user notification  
- **Keyboard interrupts**: Save state before exit to enable resumption
- **Malformed AI responses**: Default to KEEP action with error logging

## Environment Variables

Required for functionality:

- `RAINDROP_TOKEN`: Raindrop.io API token
- `ANTHROPIC_API_KEY`: Claude AI API key

## Testing Architecture

The test suite uses **pytest** with comprehensive mocking:

- **Unit tests** (`tests/unit/`): Test individual components in isolation
- **Integration tests** (`tests/integration/`): Test component interactions
- **Fixtures** (`tests/conftest.py`): Shared test data and mock objects
- **Mocking strategy**: Mock external APIs (Raindrop, Anthropic) and system calls (curses, file I/O)

Key testing patterns:

- Mock the `anthropic.Anthropic` client and `requests` for API calls
- Use `tempfile.TemporaryDirectory` for state file testing
- Patch `curses` module for UI testing without terminal interaction

## Claude AI Integration Details

The AI analysis uses a **batch processing approach** with specific prompts designed for bookmark categorization:

- **Model**: claude-3-haiku-20240307 (fast, cost-effective)
- **Input**: Title, URL, domain, excerpt (not full page content)
- **Output**: Structured decisions with reasoning
- **Categories**: Gaming, Development, Reading, Tools, Learning
- **Rate limiting**: 1-second delay between API calls
- **Error recovery**: Default to KEEP on API failures or parsing errors

The prompt engineering emphasizes ADHD-friendly decision making with clear categorization rules and conservative bias toward keeping items when uncertain.

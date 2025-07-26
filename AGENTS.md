# AGENTS.md

This repository uses the development workflow described in `CLAUDE.md`.  When making code changes you should:

* Install dependencies with `pip install -e ".[dev]"`.
* Format code with **Black** and ensure it passes in check mode.
* Lint using **ruff**.
* Type check using **mypy**.
* Run the unit tests with `pytest`.

All of these checks must succeed before committing.

The project is an AI‑powered bookmark cleanup tool for Raindrop.io built with a modular architecture. The main modules include:

* `api/raindrop_client.py` for Raindrop API access
* `ai/claude_analyzer.py` for Claude AI integration
* `ui/interfaces.py` for keyboard and text interfaces
* `state/manager.py` for persistence of session state
* `cli/main.py` for the command‑line interface

The test suite under `tests/` uses pytest with extensive mocking of external services.

# toolbelt

A small Python library of safe, typed tools that AI agents can call to work
with files and media. The core is deliberately tiny and well tested, so any
agent framework or MCP client can use it without trusting the model with the
whole filesystem.

## Goals

- Every tool is a plain function with a pydantic input model and a pydantic
  output model. No hidden global state.
- All file access goes through a `Sandbox` bound to one root directory. Path
  traversal, symlink escape and absolute paths outside the root fail with a
  typed error.
- Every tool has resource limits (bytes read, entries returned, timeout) with
  sane defaults and explicit overrides.
- Errors are structured (`code`, `message`, `hint`) so an agent can recover.
- Tool schemas are generated from the models, never written by hand.

## Non-goals

- Running arbitrary code (no `eval`, no shell, no subprocess with user input).
- Network access of any kind.
- An agent loop. toolbelt only provides the tools, not the thing that calls them.

## Stack

Python 3.12, uv, pydantic v2, pytest, ruff, mypy --strict.

## Development

```
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run mypy --strict src
```

## Status

Early work in progress. See the commit history for what exists so far.

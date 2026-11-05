# toolbelt

Python library of safe, typed tools for AI agents working with files and media.

## Layout
- `src/toolbelt/core/`: registry, sandbox, errors, limits
- `src/toolbelt/tools/`: file and media tools
- `src/toolbelt/adapters/`: schema export, MCP server, CLI
- `tests/`, `tests/fixtures/`, `evals/`

## Hard rules
- Every tool: pydantic input model, pydantic output model, registered via the decorator.
- All filesystem access goes through `Sandbox`. Never call `open` or `Path`
  methods on user-supplied paths directly.
- Tools never raise bare exceptions. Use `ToolError` with code, message, hint.
- Schemas are generated from models. Never hand-edit schema snapshots, regenerate them.
- No network access, no subprocess with user input, no `eval`/`exec`.
  Single exception: `core/media.py` runs `ffmpeg`/`ffprobe` with an argv list built only
  from validated fields (enums, bounded numbers, sandbox-resolved paths). Never
  `shell=True`, never a raw user string as an option. No other module may import `subprocess`.
- Do not add a dependency without asking. State the reason and alternatives.
- No placeholder code, TODO stubs or speculative abstractions.
- Ask before changing any public model or the registry API.

## Workflow
- Small steps, one concern per commit.
- Before every commit: `uv run ruff check`, `uv run ruff format`,
  `uv run mypy --strict src`, `uv run pytest`. Do not commit if any fails.
- Conventional Commits: feat, fix, test, refactor, docs, chore.
- Bugs get a `fix:` commit with a regression test.
- Every tool needs tests for normal input, corrupt input, oversized input and
  sandbox escape attempts.
- At the end of each phase, stop, summarize, and wait for approval.

## Commands
- Test: `uv run pytest`
- Lint: `uv run ruff check . && uv run ruff format --check .`
- Types: `uv run mypy --strict src`
- Schemas: `uv run toolbelt schema openai`
- Evals: `uv run python -m evals.run`

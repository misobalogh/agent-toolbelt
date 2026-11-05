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

- Running arbitrary code (no `eval`, no shell, no subprocess with user input). The only
  subprocess is `ffmpeg`/`ffprobe` in `core/media.py`, fed with validated arguments only.
- Network access of any kind.
- An agent loop. toolbelt only provides the tools, not the thing that calls them.

## Stack

Python 3.12, uv, pydantic v2, pytest, ruff, mypy --strict.

## Tools

| tool              | what it does                                                        |
|-------------------|---------------------------------------------------------------------|
| `list_dir`        | list a directory, hidden files optional, truncated at a limit       |
| `file_info`       | kind, size, modification time and guessed MIME type                 |
| `read_text`       | read text with encoding detection and truncation info               |
| `find_files`      | glob search, never returns files behind a symlink that leaves the root |
| `write_text`      | write UTF-8 text, only when the sandbox is created with `allow_write=True` |
| `extract_archive` | unpack zip and tar with traversal, link and zip bomb protection     |
| `media_info`      | container, duration and every stream of an audio or video file (ffprobe) |
| `convert_media`   | convert between mp3, m4a, aac, ogg, opus, flac, wav, mp4, mov, mkv, webm, gif |
| `extract_audio`   | pull the audio track of a video into an audio file                  |
| `trim_media`      | keep a time range, re-encoded or as a fast keyframe-aligned stream copy |
| `thumbnail`       | save one frame of a video as png, jpg or webp                       |
| `resize_video`    | scale to a width and/or height (aspect kept) and change the frame rate |
| `change_speed`    | speed up or slow down 0.25x to 4x, pitch kept                       |
| `adjust_volume`   | fixed gain in dB or loudness normalization                          |
| `remove_audio`    | write a copy of a video without sound                               |
| `concat_media`    | join audio files or video files in order                            |

The media tools need `ffmpeg` and `ffprobe` on `PATH`. They only write when the sandbox
is created with `allow_write=True`, except `media_info`. See "Media safety" below.

```python
from toolbelt.core.registry import default_registry
from toolbelt.core.sandbox import Sandbox
import toolbelt.tools  # registers the tools

box = Sandbox("/srv/agent-workspace")
out = default_registry.call("find_files", {"pattern": "**/*.md"}, box)
```

Failures are `ToolError`s with `code`, `message` and `hint`, for example
`outside_sandbox`, `limit_exceeded` or `write_disabled`.

## Media safety

`core/media.py` is the only module that starts a subprocess. A caller never supplies a
codec or an ffmpeg option, only validated values:

- The argv is a list, no shell. Paths come from the sandbox as absolute paths, so they
  cannot be read as options or URLs.
- Inputs may only use a short allow-list of demuxers and the `file` protocol. Playlist
  formats (hls, concat, sdp) that make ffmpeg open other files are refused, even when a
  file pretends to be a `.png` or `.mp4`.
- Output is written to a hidden temp file and moved into place only on success, so a
  failure, timeout or size overrun never leaves a partial file. Overwrite is opt-in.
- Limits: `max_media_bytes` (input size and output size), `max_media_inputs`
  (`concat_media`) and the shared `timeout_s`, which is also the ffmpeg timeout. Raise
  `timeout_s` for longer files, the default of 10 s suits short clips only.

## Schema export

`toolbelt.adapters.schema.export_schemas(registry, fmt)` renders every
registered tool as a definition for one of three targets:

| format      | shape                                              |
|-------------|----------------------------------------------------|
| `openai`    | `{"type": "function", "function": {..., "parameters"}}` |
| `anthropic` | `{"name", "description", "input_schema"}`          |
| `mcp`       | `{"name", "description", "inputSchema", "outputSchema"}` |

Schemas come from the pydantic models, nothing is written by hand. Snapshot
tests in `tests/snapshots/` make every schema change visible in review. After
an intended change, regenerate them and read the diff:

```
UPDATE_SNAPSHOTS=1 uv run pytest
git diff tests/snapshots
```

## Development

```
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run mypy --strict src
```

## Status

Done: core (registry, sandbox, errors, limits), schema export, file tools, audio and
video tools (ffmpeg).
Next: media tools for pdf and images, MCP and CLI adapters, evals.

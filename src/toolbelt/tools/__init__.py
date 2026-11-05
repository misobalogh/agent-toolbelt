"""Importing this package registers every tool in the default registry."""

from toolbelt.tools import (
    convert_media,
    extract_archive,
    extract_audio,
    file_info,
    find_files,
    list_dir,
    media_info,
    read_text,
    trim_media,
    write_text,
)

__all__ = [
    "convert_media",
    "extract_archive",
    "extract_audio",
    "file_info",
    "find_files",
    "list_dir",
    "media_info",
    "read_text",
    "trim_media",
    "write_text",
]

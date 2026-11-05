"""Importing this package registers every tool in the default registry."""

from toolbelt.tools import (
    convert_media,
    extract_archive,
    file_info,
    find_files,
    list_dir,
    media_info,
    read_text,
    write_text,
)

__all__ = [
    "convert_media",
    "extract_archive",
    "file_info",
    "find_files",
    "list_dir",
    "media_info",
    "read_text",
    "write_text",
]

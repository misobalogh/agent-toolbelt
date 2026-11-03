"""Importing this package registers every tool in the default registry."""

from toolbelt.tools import extract_archive, file_info, find_files, list_dir, read_text, write_text

__all__ = ["extract_archive", "file_info", "find_files", "list_dir", "read_text", "write_text"]

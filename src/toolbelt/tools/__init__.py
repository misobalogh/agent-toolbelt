"""Importing this package registers every tool in the default registry."""

from toolbelt.tools import file_info, list_dir, read_text

__all__ = ["file_info", "list_dir", "read_text"]

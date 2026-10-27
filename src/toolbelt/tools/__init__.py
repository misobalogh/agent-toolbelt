"""Importing this package registers every tool in the default registry."""

from toolbelt.tools import file_info, list_dir

__all__ = ["file_info", "list_dir"]

"""Importing this package registers every tool in the default registry."""

from toolbelt.tools import (
    adjust_volume,
    change_speed,
    concat_media,
    convert_media,
    extract_archive,
    extract_audio,
    file_info,
    find_files,
    list_dir,
    media_info,
    read_text,
    remove_audio,
    resize_video,
    thumbnail,
    trim_media,
    write_text,
)

__all__ = [
    "adjust_volume",
    "change_speed",
    "concat_media",
    "convert_media",
    "extract_archive",
    "extract_audio",
    "file_info",
    "find_files",
    "list_dir",
    "media_info",
    "read_text",
    "remove_audio",
    "resize_video",
    "thumbnail",
    "trim_media",
    "write_text",
]

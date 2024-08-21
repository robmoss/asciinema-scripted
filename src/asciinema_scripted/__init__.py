"""
A tool for scripting asciinema recordings and post-processing the results.
"""

from .cast import AsciiCast

from .script import (
    Script,
    Input,
    Marker,
    Comment,
    RegexReplacementFilter,
    StartMarkerFilter,
    EndMarkerFilter,
    CommentFilter,
)


__all__ = [
    'AsciiCast',
    'Script',
    'Input',
    'Marker',
    'Comment',
    'RegexReplacementFilter',
    'StartMarkerFilter',
    'EndMarkerFilter',
    'CommentFilter',
]

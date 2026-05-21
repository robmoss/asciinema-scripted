"""
A tool for scripting asciinema recordings and post-processing the results.
"""

from .cast import AsciiCast, Filter

from .script import (
    Script,
    Action,
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
    'Action',
    'Input',
    'Marker',
    'Comment',
    'Filter',
    'RegexReplacementFilter',
    'StartMarkerFilter',
    'EndMarkerFilter',
    'CommentFilter',
]

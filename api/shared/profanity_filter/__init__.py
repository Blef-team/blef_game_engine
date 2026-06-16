"""Lightweight multilingual nickname obscenity filter (no ML, layer-friendly)."""

from .filter import Filter, check, get_filter, is_offensive, LANGS
from .normalize import normalize

__all__ = ["Filter", "check", "get_filter", "is_offensive", "normalize", "LANGS"]
__version__ = "0.1.0"

"""Warm-up for your AI coding agent. Nothing like this is in the interview.

Read test_text_stats.py, then have your agent implement these two functions.
"""
from __future__ import annotations


def word_frequencies(text: str) -> dict[str, int]:
    """How often each word occurs in ``text``."""
    raise NotImplementedError


def top_words(text: str, n: int) -> list[tuple[str, int]]:
    """The ``n`` most frequent words with their counts."""
    raise NotImplementedError

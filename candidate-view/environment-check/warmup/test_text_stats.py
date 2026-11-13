"""These tests fail until warmup/text_stats.py is implemented. That is the warm-up."""
import pytest

from text_stats import top_words, word_frequencies


def test_counts_words_case_insensitively():
    assert word_frequencies("The cat saw the other cat") == {"the": 2, "cat": 2, "saw": 1, "other": 1}


def test_punctuation_is_not_part_of_a_word():
    assert word_frequencies("Stop! Stop, please... stop?") == {"stop": 3, "please": 1}


def test_apostrophes_inside_words_are_kept():
    assert word_frequencies("Don't panic, don't") == {"don't": 2, "panic": 1}


def test_empty_text_has_no_words():
    assert word_frequencies("") == {}
    assert word_frequencies("  ...  ") == {}


def test_top_words_are_ordered_by_count_then_alphabetically():
    text = "pear apple pear fig apple pear kiwi fig"
    assert top_words(text, 3) == [("pear", 3), ("apple", 2), ("fig", 2)]


def test_top_words_with_n_larger_than_the_vocabulary():
    assert top_words("b a b", 10) == [("b", 2), ("a", 1)]


def test_top_words_rejects_a_negative_n():
    with pytest.raises(ValueError):
        top_words("a b c", -1)

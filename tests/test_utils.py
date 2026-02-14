"""Unit tests for text utility functions."""

from utils.text import clean_response, normalize_whitespace, split_sentences


class TestSplitSentences:
    """Tests for split_sentences()."""

    def test_single_sentence(self):
        assert split_sentences("Hello world.") == ["Hello world."]

    def test_multiple_sentences(self):
        result = split_sentences("First sentence. Second sentence. Third one.")
        assert len(result) == 3
        assert result[0] == "First sentence."
        assert result[1] == "Second sentence."

    def test_question_and_exclamation(self):
        result = split_sentences("Is this working? Yes it is!")
        assert len(result) == 2

    def test_empty_string(self):
        result = split_sentences("")
        # Should return list with empty or single element
        assert isinstance(result, list)

    def test_no_punctuation(self):
        result = split_sentences("No punctuation here")
        assert len(result) >= 1
        assert "No punctuation here" in result[0]


class TestCleanResponse:
    """Tests for clean_response()."""

    def test_removes_asterisks(self):
        assert clean_response("**bold** text") == "bold text"

    def test_removes_hashes(self):
        assert clean_response("## Heading") == "Heading"

    def test_strips_whitespace(self):
        result = clean_response("  hello  ")
        assert result == "hello"

    def test_preserves_normal_text(self):
        text = "Normal text without markdown"
        assert clean_response(text) == text


class TestNormalizeWhitespace:
    """Tests for normalize_whitespace()."""

    def test_collapses_spaces(self):
        assert normalize_whitespace("hello   world") == "hello world"

    def test_strips_edges(self):
        assert normalize_whitespace("  hello  ") == "hello"

    def test_handles_tabs_newlines(self):
        result = normalize_whitespace("hello\t\nworld")
        assert result == "hello world"

"""
Text processing utilities for HeavyHaul AI.

Provides sentence splitting, text cleaning, and formatting functions
used across speech synthesis and LLM response processing.
"""

import re
from typing import List


def split_sentences(text: str) -> List[str]:
    """Split text into sentences for incremental TTS playback.

    Handles edge cases like decimal numbers, a.m./p.m. abbreviations,
    and currency amounts to avoid incorrect splits.

    Args:
        text: The text to split into sentences.

    Returns:
        A list of sentence strings.
    """
    result: List[str] = []
    current = ""
    i = 0

    while i < len(text):
        char = text[i]
        current += char

        if char in (".", ":"):
            prev_char = text[i - 1] if i > 0 else ""
            next_char = text[i + 1] if i < len(text) - 1 else ""

            should_split = True

            # Check for a.m. / p.m. patterns
            text_around = text[max(0, i - 5) : min(len(text), i + 3)].lower()
            if any(t in text_around for t in ("a.m", "p.m", "am.", "pm.")):
                should_split = False
            # Check for decimal numbers and currency
            elif prev_char.isdigit() and (
                next_char.isdigit()
                or (i >= 2 and text[i - 2 : i].replace("$", "").isdigit())
            ):
                should_split = False
            # Check for single letter/number abbreviations
            elif prev_char.isalnum() and (i < 2 or text[i - 2].isspace()):
                should_split = False

            if should_split:
                result.append(current.strip())
                current = ""

        i += 1

    if current.strip():
        result.append(current.strip())

    return result


def clean_response(response_text: str) -> str:
    """Clean up LLM response text by removing excessive whitespace.

    Args:
        response_text: Raw response text from LLM.

    Returns:
        Cleaned text with normalized whitespace.
    """
    return "\n".join(
        line.strip() for line in response_text.splitlines() if line.strip()
    )


def normalize_whitespace(text: str) -> str:
    """Replace multiple spaces and newlines with single spaces.

    Args:
        text: Text to normalize.

    Returns:
        Normalized text string.
    """
    text = re.sub(r"\s+", " ", text)
    text = text.replace("\n", " ")
    text = text.replace('\\"', "")
    return text.strip()

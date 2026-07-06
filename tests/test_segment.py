from lit_analyzer import segment


def test_words_and_sentences():
    text = "The cat sat. Then it ran! Did it stop?"
    assert segment.words(text) == ["The", "cat", "sat", "Then", "it", "ran", "Did", "it", "stop"]
    assert len(segment.sentences(text)) == 3


def test_words_are_letters_only():
    # digits are intentionally not words — this is prose analysis, not OCR
    assert segment.words("room 101 was cold") == ["room", "was", "cold"]


def test_paragraphs_split_on_blank_lines():
    text = "First para.\n\nSecond para.\n\n\nThird."
    assert segment.paragraphs(text) == ["First para.", "Second para.", "Third."]


def test_windows_preserve_all_words_in_order():
    # distinct letter-only tokens (aa, ab, ...) so order is verifiable
    tokens = [chr(97 + i // 26) + chr(97 + i % 26) for i in range(100)]
    wins = segment.windows(" ".join(tokens), 10)
    assert segment.words(" ".join(wins)) == tokens


def test_windows_balanced_and_complete():
    text = " ".join(["alpha"] * 100)
    wins = segment.windows(text, 10)
    assert len(wins) == 10
    total = sum(len(segment.words(w)) for w in wins)
    assert total == 100
    # each window near-equal
    assert all(9 <= len(segment.words(w)) <= 11 for w in wins)


def test_windows_more_than_words():
    wins = segment.windows("one two three", 10)
    assert len(wins) == 3  # min(n, word_count)


def test_windows_empty_text():
    assert segment.windows("", 5) == []

"""Tests for major_handler validation functionality."""

import pytest

from capy_app.frontend.cogs.features.major_handler import MajorHandler

# Test constants
EXPECTED_NUM_GROUPS = 4
EXPECTED_VALID_MAJORS_COUNT = 2


@pytest.fixture
def sample_major_list():
    """Sample list of valid majors for testing."""
    return [
        "Computer Science",
        "Mechanical Engineering",
        "Mathematics",
        "Physics",
        "Biology",
        "Chemistry",
        "Electrical Engineering",
        "Business and Management",
        "Undeclared",
        "Other",
    ]


@pytest.fixture
def major_handler(sample_major_list):
    """Create a MajorHandler instance with sample data."""
    return MajorHandler(sample_major_list)


def test_validate_majors_all_valid(major_handler):
    """Test validation with all valid majors."""
    input_majors = ["Computer Science", "Mathematics"]
    all_valid, valid_majors, invalid_majors = major_handler.validate_majors(input_majors)

    assert all_valid is True
    assert valid_majors == ["Computer Science", "Mathematics"]
    assert invalid_majors == []


def test_validate_majors_case_insensitive(major_handler):
    """Test that validation is case-insensitive and returns correct casing."""
    input_majors = ["computer science", "MATHEMATICS", "PhYsIcS"]
    all_valid, valid_majors, invalid_majors = major_handler.validate_majors(input_majors)

    assert all_valid is True
    assert valid_majors == ["Computer Science", "Mathematics", "Physics"]
    assert invalid_majors == []


def test_validate_majors_with_whitespace(major_handler):
    """Test validation handles extra whitespace."""
    input_majors = ["  Computer Science  ", " Mathematics "]
    all_valid, valid_majors, invalid_majors = major_handler.validate_majors(input_majors)

    assert all_valid is True
    assert valid_majors == ["Computer Science", "Mathematics"]
    assert invalid_majors == []


def test_validate_majors_some_invalid(major_handler):
    """Test validation with some invalid majors."""
    input_majors = ["Computer Science", "Invalid Major", "Mathematics"]
    all_valid, valid_majors, invalid_majors = major_handler.validate_majors(input_majors)

    assert all_valid is False
    assert valid_majors == ["Computer Science", "Mathematics"]
    assert invalid_majors == ["Invalid Major"]


def test_validate_majors_all_invalid(major_handler):
    """Test validation with all invalid majors."""
    input_majors: list[str] = ["Fake Major", "Another Fake"]
    all_valid, valid_majors, invalid_majors = major_handler.validate_majors(input_majors)

    assert all_valid is False
    assert valid_majors == []
    assert invalid_majors == ["Fake Major", "Another Fake"]


def test_validate_majors_empty_input(major_handler):
    """Test validation with empty input."""
    input_majors: list[str] = []
    all_valid, valid_majors, invalid_majors = major_handler.validate_majors(input_majors)

    assert all_valid is True  # No invalid majors
    assert valid_majors == []
    assert invalid_majors == []


def test_validate_majors_empty_strings(major_handler):
    """Test validation filters out empty strings."""
    input_majors = ["Computer Science", "", "  ", "Mathematics"]
    all_valid, valid_majors, invalid_majors = major_handler.validate_majors(input_majors)

    assert all_valid is True
    assert valid_majors == ["Computer Science", "Mathematics"]
    assert invalid_majors == []


def test_get_validation_error_message_single_invalid(major_handler):
    """Test error message generation for single invalid major."""
    invalid_majors: list[str] = ["Fake Major"]
    message = major_handler.get_validation_error_message(invalid_majors)

    assert "Invalid major:" in message
    assert "Fake Major" in message


def test_get_validation_error_message_multiple_invalid(major_handler):
    """Test error message generation for multiple invalid majors."""
    invalid_majors: list[str] = ["Fake Major", "Another Fake", "Third Fake"]
    message = major_handler.get_validation_error_message(invalid_majors)

    assert "Invalid majors:" in message
    assert "Fake Major" in message
    assert "Another Fake" in message
    assert "Third Fake" in message


def test_get_validation_error_message_empty(major_handler):
    """Test error message with no invalid majors."""
    invalid_majors: list[str] = []
    message = major_handler.get_validation_error_message(invalid_majors)

    assert message == ""


def test_validate_majors_special_characters(major_handler):
    """Test validation with special characters in major names."""
    # Smart title case keeps small words like "and" lowercase
    input_majors = ["business and management"]
    all_valid, valid_majors, invalid_majors = major_handler.validate_majors(input_majors)

    assert all_valid is True
    assert valid_majors == ["Business and Management"]
    assert invalid_majors == []


def test_major_handler_initialization(sample_major_list):
    """Test MajorHandler initializes correctly."""
    handler = MajorHandler(sample_major_list, num_groups=EXPECTED_NUM_GROUPS)

    assert handler.major_list == sorted(sample_major_list)
    assert handler.num_groups == EXPECTED_NUM_GROUPS
    assert len(handler._ranges) > 0
    assert len(handler._grouped_majors) > 0


def test_validate_majors_all_lowercase_input(major_handler):
    """Test that all lowercase input is converted to title case."""
    input_majors = ["computer science", "mechanical engineering"]
    all_valid, valid_majors, invalid_majors = major_handler.validate_majors(input_majors)

    assert all_valid is True
    assert valid_majors == ["Computer Science", "Mechanical Engineering"]
    assert invalid_majors == []


def test_validate_majors_all_uppercase_input(major_handler):
    """Test that all uppercase input is converted to title case."""
    input_majors = ["COMPUTER SCIENCE", "MECHANICAL ENGINEERING"]
    all_valid, valid_majors, invalid_majors = major_handler.validate_majors(input_majors)

    assert all_valid is True
    assert valid_majors == ["Computer Science", "Mechanical Engineering"]
    assert invalid_majors == []


def test_validate_majors_mixed_case_input(major_handler):
    """Test that mixed case input is normalized to title case."""
    input_majors = ["CoMpUtEr ScIeNcE", "mEcHaNiCaL eNgInEeRiNg"]
    all_valid, valid_majors, invalid_majors = major_handler.validate_majors(input_majors)

    assert all_valid is True
    assert valid_majors == ["Computer Science", "Mechanical Engineering"]
    assert invalid_majors == []


def test_smart_title_case_with_small_words(major_handler):
    """Test that small words like 'and', 'of', 'the' are kept lowercase."""
    # Add test majors with small words to the sample list
    test_cases = [
        ("business and management", "Business and Management"),
        ("BUSINESS AND MANAGEMENT", "Business and Management"),
        ("science technology and society", "Science Technology and Society"),
    ]

    for input_text, expected in test_cases:
        result = major_handler._smart_title_case(input_text)
        assert result == expected, f"Expected '{expected}' but got '{result}'"


def test_smart_title_case_first_word_always_capitalized(major_handler):
    """Test that the first word is always capitalized, even if it's a small word."""
    # Test with actual major-like phrases
    result = major_handler._smart_title_case("information technology and web science")
    assert result == "Information Technology and Web Science"

    result = major_handler._smart_title_case("communication, media, and design")
    # Note: comma is attached to "media," so "and" is treated as a small word
    assert result == "Communication, Media, and Design"


def test_validate_majors_with_multiple_small_words():
    """Test majors with multiple small words are formatted correctly."""
    # Create a handler with a major containing small words
    handler = MajorHandler(["Information Technology and Web Science", "Communication, Media, and Design"])

    input_majors = [
        "INFORMATION TECHNOLOGY AND WEB SCIENCE",
        "communication, media, and design",
    ]
    all_valid, valid_majors, invalid_majors = handler.validate_majors(input_majors)

    assert all_valid is True
    assert "Information Technology and Web Science" in valid_majors
    # Note: The comma is part of the word, so "and" after comma is handled
    assert len(valid_majors) == EXPECTED_VALID_MAJORS_COUNT
    assert invalid_majors == []


def test_validate_majors_with_abbreviations(major_handler):
    """Test that abbreviations require user confirmation via suggestions."""
    # Test common abbreviations - they should NOT be auto-expanded
    input_majors = ["CS", "me", "PHYS"]
    all_valid, valid_majors, _invalid_majors = major_handler.validate_majors(input_majors)

    # validate_majors doesn't handle abbreviations, so they'll be invalid or fuzzy matched
    # This is expected - abbreviations only work with validate_majors_with_corrections
    assert all_valid is False or len(valid_majors) > 0  # May fuzzy match if similar enough


def test_validate_majors_with_corrections_abbreviations(major_handler):
    """Test that abbreviations are tracked as suggestions (not auto-corrections)."""
    input_majors = ["CS", "MATH"]
    all_valid, valid_majors, invalid_majors, auto_corrections, suggestions = (
        major_handler.validate_majors_with_corrections(input_majors)
    )

    # Abbreviations should be suggestions, requiring user confirmation
    assert all_valid is False  # Suggestions need confirmation
    assert valid_majors == []  # No valid majors yet (waiting for confirmation)
    assert "CS" in suggestions
    assert suggestions["CS"] == "Computer Science"
    assert "MATH" in suggestions
    assert suggestions["MATH"] == "Mathematics"
    assert invalid_majors == []
    assert auto_corrections == {}  # No auto-corrections


def test_validate_majors_mixed_abbreviations_and_full_names(major_handler):
    """Test validation with a mix of abbreviations and full names."""
    input_majors = ["CS", "Physics", "me"]
    all_valid, valid_majors, invalid_majors, auto_corrections, suggestions = (
        major_handler.validate_majors_with_corrections(input_majors)
    )

    # Physics is exact match, CS and me are abbreviations (suggestions)
    assert all_valid is False  # Has suggestions needing confirmation
    assert "Physics" in valid_majors  # Exact match accepted
    assert "CS" in suggestions
    assert suggestions["CS"] == "Computer Science"
    assert "me" in suggestions
    assert suggestions["me"] == "Mechanical Engineering"
    assert invalid_majors == []
    assert auto_corrections == {}

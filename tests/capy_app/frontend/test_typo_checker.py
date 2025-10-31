"""Tests for fuzzy matching functionality in major validation."""

import pytest

from capy_app.frontend.cogs.features.major_handler import MajorHandler


@pytest.fixture
def sample_major_list():
    """Sample list of valid majors for testing."""
    return [
        "Computer Science",
        "Mechanical Engineering",
        "Aeronautical Engineering",
        "Business Analytics",
        "Physics",
        "Information Technology",
        "Software Engineering",
        "Industrial Engineering",
    ]


@pytest.fixture
def major_handler(sample_major_list):
    """Create a MajorHandler instance with sample data."""
    return MajorHandler(sample_major_list)


def test_fuzzy_match_single_typo(major_handler):
    """Test fuzzy matching with single character typos."""
    test_cases = [
        ("Compter Science", "Computer Science"),  # Missing 'u'
        ("Physcs", "Physics"),  # Missing 'i'
        ("Sofware Engineering", "Software Engineering"),  # Missing 't'
    ]

    for typo, expected in test_cases:
        all_valid, valid_majors, invalid_majors = major_handler.validate_majors([typo])
        assert all_valid is True
        assert expected in valid_majors
        assert invalid_majors == []


def test_fuzzy_match_swapped_letters(major_handler):
    """Test fuzzy matching with swapped letters."""
    test_cases = [
        ("Mechnical Engineering", "Mechanical Engineering"),
        ("Buisness Analytics", "Business Analytics"),
    ]

    for typo, expected in test_cases:
        all_valid, valid_majors, invalid_majors = major_handler.validate_majors([typo])
        assert all_valid is True
        assert expected in valid_majors
        assert invalid_majors == []


def test_fuzzy_match_multiple_typos(major_handler):
    """Test fuzzy matching with multiple typos."""
    test_cases = [
        ("Aeronautcal Engineering", "Aeronautical Engineering"),
        ("Infromation Technology", "Information Technology"),
        ("Conputer Scince", "Computer Science"),
    ]

    for typo, expected in test_cases:
        all_valid, valid_majors, invalid_majors = major_handler.validate_majors([typo])
        assert all_valid is True
        assert expected in valid_majors
        assert invalid_majors == []


def test_fuzzy_match_rejects_too_different(major_handler):
    """Test that fuzzy matching rejects inputs that are too different."""
    test_cases = [
        "CS",  # Too abbreviated
        "Comp",  # Too short
        "xyz",  # Completely different
    ]

    for invalid_input in test_cases:
        all_valid, valid_majors, invalid_majors = major_handler.validate_majors([invalid_input])
        assert all_valid is False
        assert invalid_input in invalid_majors


def test_fuzzy_match_mixed_valid_and_typos(major_handler):
    """Test fuzzy matching with a mix of valid majors and typos."""
    input_majors = ["Physics", "Compter Science", "Mechnical Engineering"]
    all_valid, valid_majors, invalid_majors = major_handler.validate_majors(input_majors)

    assert all_valid is True
    assert "Physics" in valid_majors
    assert "Computer Science" in valid_majors
    assert "Mechanical Engineering" in valid_majors
    assert invalid_majors == []


def test_validate_majors_with_corrections_tracking(major_handler):
    """Test that corrections are properly tracked."""
    input_majors = ["Compter Science", "Physics"]
    all_valid, valid_majors, invalid_majors, auto_corrections, suggestions = (
        major_handler.validate_majors_with_corrections(input_majors)
    )

    assert all_valid is True
    assert "Computer Science" in valid_majors
    assert "Physics" in valid_majors
    assert "Compter Science" in auto_corrections
    assert auto_corrections["Compter Science"] == "Computer Science"
    assert invalid_majors == []
    assert suggestions == {}

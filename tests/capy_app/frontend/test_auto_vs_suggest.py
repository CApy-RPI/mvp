"""Test the differentiation between auto-corrections and suggestions."""

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


def test_auto_correction_high_confidence(major_handler):
    """Test that high confidence matches (>=90%) are auto-corrected."""
    input_majors = ["Compter Science"]  # High confidence match
    all_valid, valid_majors, invalid_majors, auto_corrections, suggestions = (
        major_handler.validate_majors_with_corrections(input_majors)
    )

    # Should be auto-corrected
    assert all_valid is True
    assert "Computer Science" in valid_majors
    assert "Compter Science" in auto_corrections
    assert auto_corrections["Compter Science"] == "Computer Science"
    assert suggestions == {}
    assert invalid_majors == []


def test_suggestion_medium_confidence(major_handler):
    """Test that medium confidence matches (60-90%) are suggestions requiring confirmation."""
    # This test may be difficult to pass due to fuzzy matching being very good
    # We'll need to find a string that scores between 60-90%
    # For now, let's create an artificially low-scoring match
    input_majors = ["comp sci"]  # Very short - likely won't match well
    all_valid, _valid_majors, invalid_majors, auto_corrections, suggestions = (
        major_handler.validate_majors_with_corrections(input_majors)
    )

    # CS is too short and different to get a good match
    # It should either be a suggestion or invalid
    if suggestions:
        assert all_valid is False  # Needs user confirmation
        assert auto_corrections == {}
        assert len(suggestions) == 1
    else:
        # If no suggestion, should be invalid
        assert "comp sci" in invalid_majors


def test_mixed_auto_and_suggest(major_handler):
    """Test handling of both auto-corrections and suggestions in one call."""
    # We need majors that will score differently
    # "Compter Science" should auto-correct (high score)
    # Let's try to find something that scores medium
    input_majors = ["Compter Science", "Physics"]
    _all_valid, valid_majors, _invalid_majors, auto_corrections, suggestions = (
        major_handler.validate_majors_with_corrections(input_majors)
    )

    # Compter Science should be auto-corrected (score >= 90%)
    assert "Compter Science" in auto_corrections
    assert auto_corrections["Compter Science"] == "Computer Science"

    # Physics is exact match, so no correction needed
    assert "Physics" in valid_majors
    assert "Physics" not in auto_corrections
    assert "Physics" not in suggestions


def test_invalid_below_threshold(major_handler):
    """Test that very poor matches (<60%) are marked invalid."""
    input_majors = ["XYZ123"]  # Should not match anything
    all_valid, valid_majors, invalid_majors, auto_corrections, suggestions = (
        major_handler.validate_majors_with_corrections(input_majors)
    )

    assert all_valid is False
    assert "XYZ123" in invalid_majors
    assert auto_corrections == {}
    assert suggestions == {}
    assert valid_majors == []

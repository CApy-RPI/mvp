"""Handles major-related operations and grouping logic."""

import logging
from math import ceil
from typing import Any

from config import settings

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL)


class MajorHandler:
    """Handles operations related to academic majors."""

    def __init__(self, major_list: list[str], num_groups: int = 4) -> None:
        """Initialize the major handler.

        Args:
            major_list: List of all available majors
            num_groups: Number of groups to split majors into (default 4)
        """
        self.major_list = sorted(major_list)
        self.num_groups = min(num_groups, 4)  # Discord limits total components
        self._ranges = self._calculate_ranges()
        self._grouped_majors = self._group_majors()

    def _calculate_ranges(self) -> dict[str, tuple[str, str]]:
        """Dynamically calculate letter ranges based on major distribution."""
        if not self.major_list:
            return {}

        # Get unique first letters and sort them
        first_letters = sorted({major[0].upper() for major in self.major_list})

        # Calculate approximately how many letters per group
        letters_per_group = ceil(len(first_letters) / self.num_groups)

        ranges = {}
        for i in range(self.num_groups):
            start_idx = i * letters_per_group
            if start_idx >= len(first_letters):
                break

            # Get the start letter for this range
            start = first_letters[start_idx]

            # Get the end letter (start of next group, or after Z)
            end_idx = min((i + 1) * letters_per_group, len(first_letters))
            end = first_letters[end_idx] if end_idx < len(first_letters) else "["

            group_id = f"major_{start}_{chr(ord(end) - 1)}"
            ranges[group_id] = (start, end)

        return ranges

    def _group_majors(self) -> dict[str, list[str]]:
        """Group majors according to calculated ranges."""
        groups: dict[str, list[str]] = {group_id: [] for group_id in self._ranges}

        for major in self.major_list:
            first_letter = major[0].upper()
            for group_id, (start, end) in self._ranges.items():
                if start <= first_letter < end:
                    groups[group_id].append(major)
                    break

        return groups

    def get_dropdown_config(self, base_config: dict[str, Any]) -> dict[str, Any]:
        """Generate dropdown configuration with current groups.

        Args:
            base_config: Base configuration from profile_config.json
        """
        config = base_config.copy()
        config["dropdowns"] = []

        for group_id, majors in self._grouped_majors.items():
            start, end = self._ranges[group_id]
            end_letter = chr(ord(end) - 1)  # Convert end range to display letter

            config["dropdowns"].append(
                {
                    "placeholder": f"Select majors {start}-{end_letter}",
                    "custom_id": group_id,
                    "min_values": 0,
                    "max_values": 2,
                    "selections": [
                        {"label": major, "value": major} for major in majors
                    ],
                }
            )

        return config

    def get_help_text(self) -> str:
        """Generate help text showing major distribution."""
        examples = {
            "major_A": ["Aeronautical Engineering", "Computer Science"],
            "major_G": ["Information Technology", "Industrial Engineering"],
            "major_M": ["Mechanical Engineering", "Physics"],
            "major_S": ["Software Engineering", "Systems Engineering"],
        }

        text = "Select your major(s) from any group (max 2 total):\n"
        for _group_id, (start, end) in self._ranges.items():
            end_letter = chr(ord(end) - 1)
            example_letter = start
            if example_letter in examples:
                examples_str = ", ".join(examples[f"major_{example_letter}"])
                text += f"• {start}-{end_letter}: {examples_str}\n"
            else:
                text += f"• {start}-{end_letter}: Various majors\n"

        return text

    def _smart_title_case(self, text: str) -> str:
        """Convert text to title case but keep small words lowercase.

        Args:
            text: The text to convert

        Returns:
            Text in smart title case format
        """
        # Words that should remain lowercase (except at the start)
        small_words = {"and", "or", "of", "the", "in", "for", "with", "to", "a", "an"}

        words = text.split()
        if not words:
            return text

        # Always capitalize the first word
        result = [words[0].capitalize()]

        # Process remaining words
        for word in words[1:]:
            if word.lower() in small_words:
                result.append(word.lower())
            else:
                result.append(word.capitalize())

        return " ".join(result)

    def validate_majors(
        self, input_majors: list[str]
    ) -> tuple[bool, list[str], list[str]]:
        """Validate a list of major names against the valid majors list.

        Accepts input in any case and normalizes to title case with small words
        (like "and", "of", etc.) kept lowercase.

        Args:
            input_majors: List of major names to validate

        Returns:
            A tuple containing:
            - bool: True if all majors are valid, False otherwise
            - list[str]: List of valid majors in smart title case format
            - list[str]: List of invalid majors from the input
        """
        valid_majors = []
        invalid_majors = []

        # Create a case-insensitive lookup dictionary for valid majors
        major_lookup = {major.lower(): major for major in self.major_list}

        for major in input_majors:
            major_stripped = major.strip()
            if not major_stripped:
                continue

            # Check if major exists (case-insensitive)
            major_lower = major_stripped.lower()
            if major_lower in major_lookup:
                # Normalize to smart title case
                title_cased = self._smart_title_case(major_stripped)
                valid_majors.append(title_cased)
            else:
                invalid_majors.append(major_stripped)

        all_valid = len(invalid_majors) == 0
        return all_valid, valid_majors, invalid_majors

    def get_validation_error_message(self, invalid_majors: list[str]) -> str:
        """Generate a user-friendly error message for invalid majors.

        Args:
            invalid_majors: List of invalid major names

        Returns:
            A formatted error message string
        """
        if not invalid_majors:
            return ""

        if len(invalid_majors) == 1:
            msg = f"❌ Invalid major: **{invalid_majors[0]}**\n"
        else:
            majors_list = ", ".join(f"**{m}**" for m in invalid_majors)
            msg = f"❌ Invalid majors: {majors_list}\n"

        msg += "\n📋 Please enter valid majors from the list. "
        msg += "You can view all valid majors in the dropdown or check majors.txt."
        return msg

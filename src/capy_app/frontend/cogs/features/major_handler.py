"""Handles major-related operations and grouping logic."""

import logging
from typing import Dict, List, Tuple
from math import ceil

from config import settings

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL)


class MajorHandler:
    """Handles operations related to academic majors."""

    def __init__(self, major_list: List[str], num_groups: int = 4) -> None:
        """Initialize the major handler.

        Args:
            major_list: List of all available majors
            num_groups: Number of groups to split majors into (default 4)
        """
        self.major_list = sorted(major_list)
        self.num_groups = min(num_groups, 4)  # Discord limits total components
        self._ranges = self._calculate_ranges()
        self._grouped_majors = self._group_majors()

    def _calculate_ranges(self) -> Dict[str, Tuple[str, str]]:
        """Dynamically calculate letter ranges based on major distribution."""
        if not self.major_list:
            return {}

        # Get unique first letters and sort them
        first_letters = sorted(set(major[0].upper() for major in self.major_list))

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

            group_id = f"major_{start}_{chr(ord(end)-1)}"
            ranges[group_id] = (start, end)

        return ranges

    def _group_majors(self) -> Dict[str, List[str]]:
        """Group majors according to calculated ranges."""
        groups = {group_id: [] for group_id in self._ranges}

        for major in self.major_list:
            first_letter = major[0].upper()
            for group_id, (start, end) in self._ranges.items():
                if start <= first_letter < end:
                    groups[group_id].append(major)
                    break

        return groups

    def get_dropdown_config(self, base_config: dict) -> dict:
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
        for group_id, (start, end) in self._ranges.items():
            end_letter = chr(ord(end) - 1)
            example_letter = start
            if example_letter in examples:
                examples_str = ", ".join(examples[f"major_{example_letter}"])
                text += f"• {start}-{end_letter}: {examples_str}\n"
            else:
                text += f"• {start}-{end_letter}: Various majors\n"

        return text

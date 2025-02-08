"""Profile-specific view classes for Discord interactions.

This module provides the UI components for profile management:
- Profile creation/editing modal
- Major selection view
- Email verification view

#TODO: Add profile customization views
#TODO: Add profile privacy settings view
"""

import asyncio
import datetime
from typing import Optional

import discord
from frontend.utils.interactions.view_bases import BaseDropdownView
from backend.db.documents.user import User


class ProfileModal(discord.ui.Modal):
    """Modal for creating/updating user profile information."""

    def __init__(self, user: Optional[User] = None) -> None:
        """Initialize the profile modal.

        Args:
            user: Optional user for pre-filling update forms
        """
        super().__init__(title="Create Profile")
        self.add_item(
            discord.ui.TextInput(label="First Name", placeholder="John", required=True)
        )
        self.add_item(
            discord.ui.TextInput(label="Last Name", placeholder="Smith", required=True)
        )
        self.add_item(
            discord.ui.TextInput(
                label="Graduation Year",
                placeholder="2025",
                required=True,
                min_length=4,
                max_length=4,
            )
        )
        self.add_item(
            discord.ui.TextInput(
                label="Student ID",
                placeholder="123456789",
                required=True,
                min_length=9,
                max_length=9,
            )
        )
        self.add_item(
            discord.ui.TextInput(
                label="School Email", placeholder="smithj@rpi.edu", required=True
            )
        )

        if user:  # Pre-fill if updating
            self.children[0].default = user.profile.name.first
            self.children[1].default = user.profile.name.last
            self.children[2].default = user.profile.graduation_year
            self.children[3].default = user.profile.student_id
            self.children[4].default = user.profile.school_email

    async def on_submit(self, interaction: discord.Interaction) -> bool:
        """Handle modal submission and validation.

        Args:
            interaction: The Discord interaction

        Returns:
            bool: Whether the submission was valid

        #TODO: Add more robust validation
        #TODO: Add custom error messages
        """
        await interaction.response.defer(ephemeral=True)
        self.interaction = interaction

        # Validate graduation year
        try:
            grad_year = int(self.children[2].value)
            current_year = datetime.datetime.now().year
            if not (current_year <= grad_year <= current_year + 6):
                await interaction.followup.send(
                    "Invalid graduation year. Must be between current year and 6 years in the future.",
                    ephemeral=True,
                )
                return False
        except ValueError:
            await interaction.followup.send(
                "Graduation year must be a valid number.", ephemeral=True
            )
            return False

        # Validate student ID
        try:
            student_id = int(self.children[3].value)
            if not (100000000 <= student_id <= 999999999):
                await interaction.followup.send(
                    "Student ID must be a 9-digit number.", ephemeral=True
                )
                return False
        except ValueError:
            await interaction.followup.send(
                "Student ID must be a valid number.", ephemeral=True
            )
            return False

        # Validate email
        email = self.children[4].value.lower()
        if not email.endswith(".edu"):
            await interaction.followup.send(
                "Please use a valid school email address.", ephemeral=True
            )
            return False

        return True


class MajorView(BaseDropdownView):
    """Major selection view with dropdown and accept/cancel buttons."""

    def __init__(
        self, major_list: list[str], current_majors: Optional[list[str]] = None
    ) -> None:
        """Initialize the major selection view.

        Args:
            major_list: List of available majors
            current_majors: Optional list of currently selected majors

        #TODO: Add major categories
        #TODO: Add major search/filter
        """
        super().__init__()
        self.selected_majors = current_majors or ["Undeclared"]

        select = discord.ui.Select(
            placeholder="Select your major(s)...",
            min_values=1,
            max_values=min(3, len(major_list or ["Undeclared"])),
            options=[
                discord.SelectOption(label=major, value=major)
                for major in (major_list or ["Undeclared"])[:25]
            ],
            row=0,
        )

        async def select_callback(interaction: discord.Interaction) -> None:
            self.selected_majors = select.values
            await interaction.response.defer()

        select.callback = select_callback
        self.add_item(select)


class EmailVerificationView(discord.ui.View):
    """View for email verification code entry."""

    def __init__(self) -> None:
        """Initialize the email verification view."""
        super().__init__()
        self.verification_code = None

        async def button_callback(interaction: discord.Interaction) -> None:
            modal = discord.ui.Modal(title="Email Verification")
            modal.add_item(
                discord.ui.TextInput(
                    label="Verification Code",
                    placeholder="Enter the 6-digit code",
                    min_length=6,
                    max_length=6,
                    required=True,
                )
            )

            async def modal_callback(interaction: discord.Interaction) -> None:
                await interaction.response.defer(ephemeral=True)
                self.verification_code = modal.children[0].value
                self.stop()

            modal.on_submit = modal_callback
            await interaction.response.send_modal(modal)

        self.add_item(
            discord.ui.Button(
                label="Enter Verification Code",
                style=discord.ButtonStyle.primary,
                custom_id="verify",
            )
        )
        self.children[0].callback = button_callback

    async def wait_for_verification(self, timeout: float = 300.0) -> Optional[str]:
        """Wait for the user to enter a verification code.

        Args:
            timeout: Time in seconds to wait for verification

        Returns:
            The verification code if entered, None if timed out

        #TODO: Add code retry limit
        #TODO: Add code expiration
        """
        try:
            await asyncio.wait_for(self.wait(), timeout=timeout)
            return self.verification_code
        except asyncio.TimeoutError:
            return None

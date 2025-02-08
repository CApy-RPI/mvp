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
from typing import Optional, List, Any, cast, Union
import discord
from discord import ui
from discord.interactions import Interaction
from frontend.utils.interactions.view_bases import BaseDropdownView
from backend.db.documents.user import User


class ProfileModal(ui.Modal, title="Create Profile"):
    first_name: ui.TextInput[Any] = ui.TextInput(
        label="First Name", placeholder="John", required=True
    )
    last_name: ui.TextInput[Any] = ui.TextInput(
        label="Last Name", placeholder="Smith", required=True
    )
    graduation_year: ui.TextInput[Any] = ui.TextInput(
        label="Graduation Year",
        placeholder="2025",
        required=True,
        min_length=4,
        max_length=4,
    )
    student_id: ui.TextInput[Any] = ui.TextInput(
        label="Student ID",
        placeholder="123456789",
        required=True,
        min_length=9,
        max_length=9,
    )
    school_email: ui.TextInput[Any] = ui.TextInput(
        label="School Email", placeholder="smithj@rpi.edu", required=True
    )

    def __init__(self, user: Optional[User] = None) -> None:
        super().__init__()
        if user:
            self.first_name.default = user.profile.name.first
            self.last_name.default = user.profile.name.last
            self.graduation_year.default = str(user.profile.graduation_year)
            self.student_id.default = str(user.profile.student_id)
            self.school_email.default = user.profile.school_email

    async def on_submit(self, interaction: Interaction[discord.Client]) -> None:
        await interaction.response.defer(ephemeral=True)
        self.interaction = interaction

        try:
            grad_year = int(self.graduation_year.value)
            current_year = datetime.datetime.now().year
            if not (current_year <= grad_year <= current_year + 6):
                await interaction.followup.send(
                    "Invalid graduation year. Must be between current year and 6 years in the future.",
                    ephemeral=True,
                )
                return

            student_id = int(self.student_id.value)
            if not (100000000 <= student_id <= 999999999):
                await interaction.followup.send(
                    "Student ID must be a 9-digit number.", ephemeral=True
                )
                return

            email = self.school_email.value.lower()
            if not email.endswith(".edu"):
                await interaction.followup.send(
                    "Please use a valid school email address.", ephemeral=True
                )
                return

        except ValueError:
            await interaction.followup.send(
                "Invalid input. Please check your entries.", ephemeral=True
            )
            return


class MajorView(BaseDropdownView):
    def __init__(
        self, major_list: List[str], current_majors: Optional[List[str]] = None
    ) -> None:
        super().__init__()
        self.selected_majors = current_majors or ["Undeclared"]

        select = ui.Select[ui.View](
            placeholder="Select your major(s)...",
            min_values=1,
            max_values=min(3, len(major_list or ["Undeclared"])),
            options=[
                discord.SelectOption(label=major, value=major)
                for major in (major_list or ["Undeclared"])[:25]
            ],
            row=0,
        )
        select.callback = self._on_select
        self.add_item(select)

    async def _on_select(self, interaction: Interaction[discord.Client]) -> None:
        select = cast(ui.Select[ui.View], interaction.data)
        self.selected_majors = select.values
        await interaction.response.defer()


class EmailVerificationView(ui.View):
    def __init__(self) -> None:
        super().__init__()
        self.verification_code: Optional[str] = None

        verify_button = ui.Button[ui.View](
            label="Enter Verification Code",
            style=discord.ButtonStyle.primary,
            custom_id="verify",
        )
        verify_button.callback = self._on_verify
        self.add_item(verify_button)

    async def _on_verify(self, interaction: Interaction[discord.Client]) -> None:
        modal = ui.Modal(title="Email Verification")
        code_input = ui.TextInput[Any](
            label="Verification Code",
            placeholder="Enter the 6-digit code",
            min_length=6,
            max_length=6,
            required=True,
        )
        modal.add_item(code_input)

        async def on_modal_submit(modal_interaction: Interaction[discord.Client]) -> None:
            await modal_interaction.response.defer(ephemeral=True)
            if isinstance(code_input, ui.TextInput):
                self.verification_code = code_input.value
            self.stop()

        modal.on_submit = on_modal_submit
        await interaction.response.send_modal(modal)

    async def wait_for_verification(self, timeout: float = 300.0) -> Optional[str]:
        try:
            await asyncio.wait_for(self.wait(), timeout=timeout)
            return self.verification_code
        except asyncio.TimeoutError:
            return None

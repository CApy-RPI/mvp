"""Profile-specific view classes."""

import asyncio
import discord
from frontend.utils.interactions.view_bases import BaseDropdownView
from backend.db.documents.user import User


class ProfileModal(discord.ui.Modal):
    """Modal for creating/updating user profile information."""

    def __init__(self, user: User | None = None):
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

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)


class MajorView(BaseDropdownView):
    """Major selection view with dropdown and accept/cancel buttons."""

    def __init__(self, major_list: list[str], current_majors: list[str] | None = None):
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
        )

        async def select_callback(interaction: discord.Interaction):
            self.selected_majors = select.values
            await interaction.response.defer()

        select.callback = select_callback
        self.add_item(select)


class EmailVerificationView(discord.ui.View):
    """View for email verification code entry."""

    def __init__(self):
        super().__init__()
        self.verification_code = None

        async def button_callback(interaction: discord.Interaction):
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

            async def modal_callback(interaction: discord.Interaction):
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

    async def wait_for_verification(self, timeout: float = 300.0) -> str | None:
        try:
            await asyncio.wait_for(self.wait(), timeout=timeout)
            return self.verification_code
        except asyncio.TimeoutError:
            return None

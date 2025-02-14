"""Profile-specific view classes for Discord interactions."""

from typing import Optional, List, Dict
import datetime
import discord
from discord import TextStyle, ButtonStyle
from backend.db.documents.user import User

from frontend.interactions.bases.modal_base import (
    DynamicModal,
    DynamicModalView,
    create_modal_view,
)
from frontend.interactions.bases.dropdown_base import MultiSelectorView


class ProfileModal(DynamicModal):
    """Profile creation/editing modal without button trigger."""

    def __init__(self, user: Optional[User] = None) -> None:
        super().__init__(title="Create Profile")

        self.add_field(
            label="First Name",
            placeholder="John",
            default=user.profile.name.first if user else "",
        )

        self.add_field(
            label="Last Name",
            placeholder="Smith",
            default=user.profile.name.last if user else "",
        )

        self.add_field(
            label="Graduation Year",
            placeholder="2025",
            min_length=4,
            max_length=4,
            default=str(user.profile.graduation_year) if user else "",
        )

        self.add_field(
            label="Student ID",
            placeholder="123456789",
            min_length=9,
            max_length=9,
            default=str(user.profile.student_id) if user else "",
        )

        self.add_field(
            label="School Email",
            placeholder="smithj@rpi.edu",
            default=user.profile.school_email if user else "",
        )

        self.success = False

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            grad_year = int(self.children[2].value)
            current_year = datetime.datetime.now().year
            if not (current_year <= grad_year <= current_year + 6):
                await interaction.followup.send(
                    "Invalid graduation year. Must be between current year and 6 years in the future.",
                    ephemeral=True,
                )
                return

            student_id = int(self.children[3].value)
            if not (100000000 <= student_id <= 999999999):
                await interaction.followup.send(
                    "Student ID must be a 9-digit number.", ephemeral=True
                )
                return

            email = self.children[4].value.lower()
            if not email.endswith(".edu"):
                await interaction.followup.send(
                    "Please use a valid school email address.", ephemeral=True
                )
                return

            self.success = True
            self.values = {
                "first_name": self.children[0].value,
                "last_name": self.children[1].value,
                "graduation_year": self.children[2].value,
                "student_id": self.children[3].value,
                "school_email": self.children[4].value.lower(),
            }
        except ValueError:
            await interaction.followup.send(
                "Invalid input. Please check your entries.", ephemeral=True
            )


class EmailVerificationView(DynamicModalView):
    """Email verification with button trigger."""

    def __init__(self) -> None:
        modal = DynamicModal(title="Email Verification")
        modal.add_field(
            label="Verification Code",
            placeholder="Enter the 6-digit code",
            min_length=6,
            max_length=6,
            required=True,
            style=TextStyle.short,
            custom_id="verification_code",
        )

        super().__init__(
            modal=modal,
            button_label="Enter Verification Code",
            button_style=ButtonStyle.primary,
        )

        # Add custom validation
        async def validate_submit(interaction: discord.Interaction) -> None:
            await interaction.response.defer(ephemeral=True)
            code = self.modal.children[0].value
            if not code.isdigit() or len(code) != 6:
                await interaction.followup.send(
                    "Invalid verification code format.", ephemeral=True
                )
                return
            self.modal.success = True
            self.modal.values = {"verification_code": code}

        self.modal.on_submit = validate_submit


class MajorSelector(MultiSelectorView):
    """Dropdown for major selection."""

    def __init__(
        self, major_list: List[str], current_majors: Optional[List[str]] = None
    ) -> None:
        super().__init__(timeout=180.0)

        options_dict: Dict[str, Dict[str, str]] = {
            major: {"value": major, "description": f"Select {major} as your major"}
            for major in (major_list or ["Undeclared"])
        }

        self.add_dropdown(
            options_dict=options_dict,
            placeholder="Select your major(s)...",
            min_values=1,
            max_values=min(3, len(major_list or ["Undeclared"])),
            custom_id="major_selector",
        )

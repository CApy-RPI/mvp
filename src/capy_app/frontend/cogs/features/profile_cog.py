# stl imports
import asyncio
import logging
import random

# third-party imports
import discord
from discord import app_commands
from discord.ext import commands

# local imports
from config import settings
from backend.db.database import Database as db
from backend.db.documents.user import User, UserProfile, UserName
from backend.modules.email import Email
from frontend.utils.interactions.view_bases import BaseDropdownView, ConfirmDeleteView


class ProfileModal(discord.ui.Modal):
    def __init__(self, user=None):
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

        # Add major selection dropdown
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

    # Override accept/cancel from BaseDropdownView to handle majors
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Accept button updates the selected majors."""
        await super().accept(interaction, button)
        # selected_majors already contains the latest selection

    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel button restores original majors or sets to Undeclared."""
        await super().cancel(interaction, button)
        # Keep original majors by not changing selected_majors


class EmailVerificationView(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.modal = None
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

    async def wait_for_verification(self, timeout=300.0):
        try:
            await asyncio.wait_for(self.wait(), timeout=timeout)
            return self.verification_code
        except asyncio.TimeoutError:
            return None


class EmailVerifier:
    def __init__(self):
        self._codes = {}
        self._email_client = Email()

    def generate_code(self, user_id: int, email: str) -> str:
        code = "".join(str(random.randint(0, 9)) for _ in range(6))
        self._codes[user_id] = (code, email)
        return code

    def verify_code(self, user_id: int, code: str) -> bool:
        if user_id not in self._codes:
            return False
        stored_code, _ = self._codes[user_id]
        is_valid = code == stored_code
        if is_valid:
            del self._codes[user_id]
        return is_valid


class ProfileCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = logging.getLogger(
            f"discord.cog.{self.__class__.__name__.lower()}"
        )
        self.major_list = self.load_major_list()
        self.email_verifier = EmailVerifier()

    def load_major_list(self):
        try:
            with open(settings.MAJORS_PATH, "r") as f:
                majors = [line.strip() for line in f.readlines()]
                if not majors:
                    self.logger.warning("majors.txt is empty")
                return majors
        except FileNotFoundError:
            self.logger.error("majors.txt not found")
        except Exception as e:
            self.logger.error(f"Error loading majors: {e}")

    @app_commands.guilds(discord.Object(id=settings.DEBUG_GUILD_ID))
    @app_commands.command(name="profile", description="Manage your profile")
    @app_commands.describe(action="The action to perform with your profile")
    @app_commands.choices(
        action=[
            app_commands.Choice(name="create", value="create"),
            app_commands.Choice(name="update", value="update"),
            app_commands.Choice(name="show", value="show"),
            app_commands.Choice(name="delete", value="delete"),
        ]
    )
    async def profile(self, interaction: discord.Interaction, action: str):
        """Handle profile actions."""
        if action in ["create", "update"]:  # These use modals, don't defer
            if action == "create":
                await self.create_profile(interaction)
            else:
                await self.update_profile(interaction)
        else:  # Show and delete can defer
            await interaction.response.defer(ephemeral=True)
            if action == "delete":
                await self.delete_profile(interaction)
            elif action == "show":
                await self.show_profile(interaction)

    async def create_profile(self, interaction: discord.Interaction):
        """Create a new user profile."""
        user = db.get_document(User, interaction.user.id)
        if user:
            await interaction.response.send_message(
                "You already have a profile. Use /profile update to modify it.",
                ephemeral=True,
            )
            return

        # Show modal first
        modal = ProfileModal()
        await interaction.response.send_modal(modal)
        await modal.wait()

        # Now we can use edit_original_response for subsequent messages
        # Validate inputs
        if not modal.children[2].value.isdigit():
            await interaction.edit_original_response(content="Invalid graduation year!")
            return

        if not modal.children[3].value.isdigit():
            await interaction.edit_original_response(content="Invalid student ID!")
            return

        if not modal.children[4].value.endswith("edu"):
            await interaction.edit_original_response(content="Invalid School email!")
            return

        # Show major selection first
        major_view = MajorView(self.major_list)
        await interaction.edit_original_response(
            content="Select your major(s):", view=major_view
        )
        await major_view.wait()

        if not major_view.value:  # Cancelled
            selected_majors = ["Undeclared"]
        else:
            selected_majors = major_view.selected_majors

        # Now handle email verification
        # Send verification code while user is selecting major
        verification_code = self.email_verifier.generate_code(
            interaction.user.id, modal.children[4].value
        )
        email_result = self.email_verifier._email_client.send_mail(
            modal.children[4].value, verification_code
        )

        if not email_result:
            await interaction.edit_original_response(
                content="Failed to send verification email. Please try again."
            )
            return

        # Show verification button
        verify_view = EmailVerificationView()
        await interaction.edit_original_response(
            content="Please check your email and spam for a verification code, then click the button below to verify:",
            view=verify_view,
        )

        submitted_code = await verify_view.wait_for_verification(timeout=300.0)
        if not submitted_code:
            await interaction.edit_original_response(
                content="Verification timed out. Please try again."
            )
            return

        if not self.email_verifier.verify_code(interaction.user.id, submitted_code):
            await interaction.edit_original_response(
                content="Invalid verification code. Please try again."
            )
            return

        # Create user profile
        new_user = User(
            _id=interaction.user.id,
            profile=UserProfile(
                name=UserName(
                    first=modal.children[0].value, last=modal.children[1].value
                ),
                major=selected_majors,
                graduation_year=modal.children[2].value,
                school_email=modal.children[4].value,
                student_id=modal.children[3].value,
            ),
        )
        db.add_document(new_user)

        await interaction.edit_original_response(
            content="Profile created successfully!"
        )
        # Show the new profile
        await self.show_profile_embed(interaction, new_user)

    async def update_profile(self, interaction: discord.Interaction):
        """Update existing user profile."""
        user = db.get_document(User, interaction.user.id)
        if not user:
            await interaction.response.send_message(
                "You don't have a profile yet! Use /profile create first.",
                ephemeral=True,
            )
            return

        modal = ProfileModal(user=user)
        await interaction.response.send_modal(modal)
        await modal.wait()

        # Now we can use edit_original_response for subsequent messages
        # Verify email if changed
        if modal.children[4].value != user.profile.school_email:
            if not modal.children[4].value.endswith("edu"):
                await interaction.edit_original_response(
                    content="Invalid School email!"
                )
                return

            verification_code = self.email_verifier.generate_code(
                interaction.user.id, modal.children[4].value
            )
            email_result = self.email_verifier._email_client.send_mail(
                modal.children[4].value, verification_code
            )

            if not email_result:
                await interaction.edit_original_response(
                    content="Failed to send verification email. Please try again."
                )
                return

            view = EmailVerificationView()
            await interaction.edit_original_response(
                content="Please check your email for a verification code, then click the button below to verify:",
                view=view,
            )

            submitted_code = await view.wait_for_verification(timeout=300.0)
            if not submitted_code:
                await interaction.edit_original_response(
                    content="Verification timed out. Please try again."
                )
                return

            if not self.email_verifier.verify_code(interaction.user.id, submitted_code):
                await interaction.edit_original_response(
                    content="Invalid verification code. Please try again."
                )
                return

        # Update major selection
        major_view = MajorView(self.major_list, current_majors=user.profile.major)
        await interaction.edit_original_response(
            content="Update your major(s):",
            view=major_view,
        )

        await major_view.wait()
        if not major_view.value:  # Cancelled
            selected_majors = user.profile.major  # Keep current majors
        else:
            selected_majors = major_view.selected_majors

        updates = {
            "profile__name__first": modal.children[0].value,
            "profile__name__last": modal.children[1].value,
            "profile__graduation_year": modal.children[2].value,
            "profile__school_email": modal.children[4].value,
            "profile__student_id": modal.children[3].value,
            "profile__major": selected_majors,  # Always update majors (will be either new selection or existing ones)
        }

        db.update_document(user, updates)
        await interaction.edit_original_response(
            content="Profile updated successfully!"
        )

        # Show the updated profile
        updated_user = db.get_document(User, interaction.user.id)
        await self.show_profile_embed(interaction, updated_user)

    async def show_profile_embed(self, interaction: discord.Interaction, user: User):
        """Helper method to show profile embed."""
        embed = discord.Embed(
            title=f"{interaction.user.display_name}'s Profile",
            color=discord.Color.purple(),
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.add_field(name="First Name", value=user.profile.name.first, inline=True)
        embed.add_field(name="Last Name", value=user.profile.name.last, inline=True)
        embed.add_field(name="Major", value=", ".join(user.profile.major), inline=True)
        embed.add_field(
            name="Graduation Year", value=user.profile.graduation_year, inline=True
        )
        embed.add_field(
            name="School Email", value=user.profile.school_email, inline=True
        )
        embed.add_field(name="Student ID", value=user.profile.student_id, inline=True)

        await interaction.edit_original_response(embed=embed, content=None, view=None)

    async def show_profile(self, interaction: discord.Interaction):
        """Display user profile."""
        user = db.get_document(User, interaction.user.id)
        if not user:
            await interaction.edit_original_response(
                content="You don't have a profile yet! Use /profile create first."
            )
            return

        await self.show_profile_embed(interaction, user)

    async def delete_profile(self, interaction: discord.Interaction):
        """Delete user profile with confirmation."""
        user = db.get_document(User, interaction.user.id)
        if not user:
            await interaction.edit_original_response(
                content="You don't have a profile to delete."
            )
            return

        view = ConfirmDeleteView()
        await interaction.edit_original_response(
            content="⚠️ Are you sure you want to delete your profile? This action cannot be undone.",
            view=view,
        )

        await view.wait()
        if view.value:
            db.delete_document(user)
            await interaction.edit_original_response(
                content="Your profile has been deleted.", view=None
            )
        else:
            await interaction.edit_original_response(
                content="Profile deletion cancelled.", view=None
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(ProfileCog(bot))

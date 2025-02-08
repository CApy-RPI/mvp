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


class MajorView(discord.ui.View):
    def __init__(self, major_list):
        super().__init__(timeout=180.0)
        self.message = None
        if not major_list:
            major_list = ["Undeclared"]

        major_list = major_list[:25]
        self.selected_majors = None
        self.skipped = False

        select = discord.ui.Select(
            placeholder="Select your major(s)...",
            min_values=1,
            max_values=min(3, len(major_list)),
            options=[
                discord.SelectOption(label=major, value=major) for major in major_list
            ],
        )

        async def select_callback(interaction: discord.Interaction):
            self.selected_majors = select.values
            await interaction.response.defer()
            if not self.skipped:  # Only stop if not skipped
                self.stop()

        select.callback = select_callback
        self.add_item(select)

        # Add skip button
        skip_button = discord.ui.Button(
            label="Skip", style=discord.ButtonStyle.secondary
        )

        async def skip_callback(interaction: discord.Interaction):
            await interaction.response.defer()
            self.skipped = True
            self.stop()

        skip_button.callback = skip_callback
        self.add_item(skip_button)

    async def on_timeout(self) -> None:
        if self.message:
            await self.message.delete()

    async def wait_for_majors(self, timeout=180.0):
        try:
            await self.wait()
            if self.skipped:
                return "skip"
            return self.selected_majors or None
        except TimeoutError:
            return None


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


class DeleteConfirmView(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.value = None

    @discord.ui.button(label="Confirm Delete", style=discord.ButtonStyle.danger)
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()
        self.value = True
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.value = False
        self.stop()


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
        if action == "delete":
            await self.delete_profile(interaction)
        else:
            if action == "create":
                await self.create_profile(interaction)
            elif action == "update":
                await self.update_profile(interaction)
            elif action == "show":
                await self.show_profile(interaction)

    async def create_profile(self, interaction: discord.Interaction):
        user = db.get_document(User, interaction.user.id)
        if user:
            await interaction.response.send_message(
                "You already have a profile. Use /profile update to modify it.",
                ephemeral=True,
            )
            return

        modal = ProfileModal()
        await interaction.response.send_modal(modal)
        await modal.wait()

        # Validate inputs
        if not modal.children[2].value.isdigit():
            await interaction.followup.send("Invalid graduation year!", ephemeral=True)
            return

        if not modal.children[3].value.isdigit():
            await interaction.followup.send("Invalid student ID!", ephemeral=True)
            return

        if not modal.children[4].value.endswith("edu"):
            await interaction.followup.send("Invalid School email!", ephemeral=True)
            return

        # Show major selection first
        major_view = MajorView(self.major_list)
        major_view.message = await interaction.followup.send(
            "Select your major(s):", view=major_view, ephemeral=True
        )

        selected_majors = await major_view.wait_for_majors(timeout=180.0)
        if major_view.message:
            await major_view.message.delete()
        
        if selected_majors is None:  # Timed out
            await interaction.followup.send(
                "Major selection timed out. Please try again.", ephemeral=True
            )
            return

        # Now handle email verification
        # Send verification code while user is selecting major
        verification_code = self.email_verifier.generate_code(
            interaction.user.id, modal.children[4].value
        )
        email_result = self.email_verifier._email_client.send_mail(
            modal.children[4].value, verification_code
        )

        if not email_result:
            await interaction.followup.send(
                "Failed to send verification email. Please try again.", ephemeral=True
            )
            return

        # Show verification button
        verify_view = EmailVerificationView()
        await interaction.followup.send(
            "Please check your email and spam for a verification code, then click the button below to verify:",
            view=verify_view,
            ephemeral=True,
        )

        submitted_code = await verify_view.wait_for_verification(timeout=300.0)
        if not submitted_code:
            await interaction.followup.send(
                "Verification timed out. Please try again.", ephemeral=True
            )
            return

        if not self.email_verifier.verify_code(interaction.user.id, submitted_code):
            await interaction.followup.send(
                "Invalid verification code. Please try again.", ephemeral=True
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

        await interaction.followup.send("Profile created successfully!", ephemeral=True)
        # Show the new profile
        await self.show_profile_embed(interaction, new_user)

    async def update_profile(self, interaction: discord.Interaction):
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

        # Verify email if changed
        if modal.children[4].value != user.profile.school_email:
            if not modal.children[4].value.endswith("edu"):
                await interaction.followup.send("Invalid School email!", ephemeral=True)
                return

            verification_code = self.email_verifier.generate_code(
                interaction.user.id, modal.children[4].value
            )
            email_result = self.email_verifier._email_client.send_mail(
                modal.children[4].value, verification_code
            )

            if not email_result:
                await interaction.followup.send(
                    "Failed to send verification email. Please try again.",
                    ephemeral=True,
                )
                return

            view = EmailVerificationView()
            await interaction.followup.send(
                "Please check your email for a verification code, then click the button below to verify:",
                view=view,
                ephemeral=True,
            )

            submitted_code = await view.wait_for_verification(timeout=300.0)
            if not submitted_code:
                await interaction.followup.send(
                    "Verification timed out. Please try again.", ephemeral=True
                )
                return

            if not self.email_verifier.verify_code(interaction.user.id, submitted_code):
                await interaction.followup.send(
                    "Invalid verification code. Please try again.", ephemeral=True
                )
                return

        # Update major selection
        major_view = MajorView(self.major_list)
        major_view.message = await interaction.followup.send(
            "Update your major(s) or click Skip to keep current majors:",
            view=major_view,
            ephemeral=True,
        )

        selected_majors = await major_view.wait_for_majors(timeout=180.0)
        if major_view.message:
            await major_view.message.delete()

        if selected_majors is None:  # Timed out
            await interaction.followup.send(
                "Major selection timed out. Please try again.", ephemeral=True
            )
            return
        elif selected_majors == "skip":
            # Keep existing majors
            selected_majors = user.profile.major

        updates = {
            "profile__name__first": modal.children[0].value,
            "profile__name__last": modal.children[1].value,
            "profile__graduation_year": modal.children[2].value,
            "profile__school_email": modal.children[4].value,
            "profile__student_id": modal.children[3].value,
            "profile__major": selected_majors,  # Always update majors (will be either new selection or existing ones)
        }

        db.update_document(user, updates)
        await interaction.followup.send("Profile updated successfully!", ephemeral=True)

        # Show the updated profile
        updated_user = db.get_document(User, interaction.user.id)
        await self.show_profile_embed(interaction, updated_user)

    async def show_profile_embed(self, interaction: discord.Interaction, user: User):
        """Helper method to show profile embed"""
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

        await interaction.followup.send(embed=embed, ephemeral=True)

    async def show_profile(self, interaction: discord.Interaction):
        user = db.get_document(User, interaction.user.id)
        if not user:
            await interaction.response.send_message(
                "You don't have a profile yet! Use /profile create first.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        await self.show_profile_embed(interaction, user)

    async def delete_profile(self, interaction: discord.Interaction):
        """Delete user profile with confirmation."""
        user = db.get_document(User, interaction.user.id)
        if not user:
            await interaction.response.send_message(
                "You don't have a profile to delete.", ephemeral=True
            )
            return

        view = DeleteConfirmView()
        await interaction.response.send_message(
            "⚠️ Are you sure you want to delete your profile? This action cannot be undone.",
            view=view,
            ephemeral=True,
        )

        await view.wait()
        if view.value:
            db.delete_document(user)
            await interaction.followup.send(
                "Your profile has been deleted.", ephemeral=True
            )
        else:
            await interaction.followup.send(
                "Profile deletion cancelled.", ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(ProfileCog(bot))
`

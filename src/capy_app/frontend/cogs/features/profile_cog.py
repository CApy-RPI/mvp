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
from frontend.utils.interactions.view_bases import ConfirmDeleteView
from frontend.utils.interactions.profile.handlers import EmailVerifier
from frontend.utils.interactions.profile.views import (
    MajorView,
    ProfileModal,
    EmailVerificationView,
)


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

        if not modal.interaction:
            return

        # Use followup instead of response.defer since modal.interaction has already been responded to
        msg = await modal.interaction.followup.send(
            content="Select your major(s):", view=MajorView(self.major_list), wait=True
        )

        # Get the view from the message
        major_view = msg.view
        await major_view.wait()

        if not major_view.value:  # Cancelled
            selected_majors = ["Undeclared"]
        else:
            selected_majors = major_view.selected_majors

        # Handle email verification
        verification_code = self.email_verifier.generate_code(
            interaction.user.id, modal.children[4].value
        )
        email_result = self.email_verifier._email_client.send_mail(
            modal.children[4].value, verification_code
        )

        if not email_result:
            await msg.edit(
                content="Failed to send verification email. Please try again.",
                view=None,
            )
            return

        # Show verification button
        verify_view = EmailVerificationView()
        await msg.edit(
            content="Please check your email and spam for a verification code, then click the button below to verify:",
            view=verify_view,
        )

        submitted_code = await verify_view.wait_for_verification(timeout=300.0)
        if not submitted_code:
            await msg.edit(
                content="Verification timed out. Please try again.", view=None
            )
            return

        if not self.email_verifier.verify_code(interaction.user.id, submitted_code):
            await msg.edit(
                content="Invalid verification code. Please try again.", view=None
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

        # Show the new profile immediately
        embed = discord.Embed(
            title=f"{interaction.user.display_name}'s Profile",
            color=discord.Color.purple(),
        )
        # ... rest of embed creation ...
        await msg.edit(content=None, embed=embed, view=None)

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

        if not modal.interaction:
            return

        # Use followup since modal.interaction has already been responded to
        msg = await modal.interaction.followup.send(
            content="Processing your update...", ephemeral=True, wait=True
        )

        # Verify email if changed
        if modal.children[4].value != user.profile.school_email:
            # Use the send_verification_email method
            if not self.email_verifier.send_verification_email(
                interaction.user.id, modal.children[4].value
            ):
                await msg.edit(
                    content="Failed to send verification email. Please try again."
                )
                return

            view = EmailVerificationView()
            await msg.edit(
                content="Please check your email for a verification code, then click the button below to verify:",
                view=view,
            )

            submitted_code = await view.wait_for_verification(timeout=300.0)
            if not submitted_code:
                await msg.edit(
                    content="Verification timed out. Please try again.", view=None
                )
                return

            if not self.email_verifier.verify_code(interaction.user.id, submitted_code):
                await msg.edit(
                    content="Invalid verification code. Please try again.", view=None
                )
                return

        # Update major selection
        major_view = MajorView(self.major_list, current_majors=user.profile.major)
        await msg.edit(content="Update your major(s):", view=major_view)

        await major_view.wait()
        selected_majors = (
            major_view.selected_majors if major_view.value else user.profile.major
        )

        # Update the user profile
        updates = {
            "profile__name__first": modal.children[0].value,
            "profile__name__last": modal.children[1].value,
            "profile__graduation_year": modal.children[2].value,
            "profile__school_email": modal.children[4].value,
            "profile__student_id": modal.children[3].value,
            "profile__major": selected_majors,
        }

        db.update_document(user, updates)

        # Show the updated profile
        updated_user = db.get_document(User, interaction.user.id)
        await self.show_profile_embed(msg, updated_user)

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

        await interaction.edit_original_response(content=None, embed=embed, view=None)

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

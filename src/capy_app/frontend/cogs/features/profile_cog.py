"""Profile management cog for handling user profiles.

This module provides commands and utilities for managing user profiles including:
- Profile creation and updates
- Email verification
- Major selection
- Profile display and deletion

#TODO: Add profile export/import functionality
#TODO: Add profile privacy settings
"""

import logging
from typing import Union

import discord
from discord import app_commands
from discord.ext import commands

from config import settings
from backend.db.database import Database as db
from backend.db.documents.user import User, UserProfile, UserName
from frontend.interactions.bases.view_bases import ConfirmDeleteView
from .profile_handlers import (
    EmailVerifier,
)
from .profile_views import (
    MajorView,
    ProfileModal,
    EmailVerificationView,
)


class ProfileCog(commands.Cog):
    """Profile management cog for handling user profiles."""

    def __init__(self, bot: commands.Bot) -> None:
        """Initialize the profile cog.

        Args:
            bot: The Discord bot instance
        """
        self.bot = bot
        self.logger = logging.getLogger(
            f"discord.cog.{self.__class__.__name__.lower()}"
        )
        self.major_list = self._load_major_list()
        self.email_verifier = EmailVerifier()

    def _load_major_list(self) -> list[str]:
        """Load the list of available majors from file."""
        try:
            with open(settings.MAJORS_PATH, "r", encoding="utf-8") as f:
                majors = [line.strip() for line in f.readlines() if line.strip()]
                self.logger.info(f"Loaded {len(majors)} majors from file")
                if not majors:
                    self.logger.warning("majors.txt is empty")
                return majors
        except FileNotFoundError:
            self.logger.error(f"majors.txt not found at {settings.MAJORS_PATH}")
            return ["Undeclared"]
        except Exception as e:
            self.logger.error(f"Error loading majors from {settings.MAJORS_PATH}: {e}")
            return ["Undeclared"]

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
    async def profile(self, interaction: discord.Interaction, action: str) -> None:
        """Handle profile actions.

        Args:
            interaction: The Discord interaction
            action: The action to perform (create/update/show/delete)
        """
        if action in ["create", "update"]:
            await self.handle_profile(interaction, action)
        else:  # Show and delete can defer
            await interaction.response.defer(ephemeral=True)
            if action == "delete":
                await self.delete_profile(interaction)
            elif action == "show":
                await self.show_profile(interaction)

    async def get_profile_data(
        self, interaction: discord.Interaction, action: str, user: User | None
    ) -> ProfileModal | None:
        """Get profile data from modal.

        Args:
            interaction: The Discord interaction
            action: The action being performed
            user: The existing user if updating

        Returns:
            Tuple of (modal, message) if successful, None otherwise
        """
        modal = ProfileModal(user=user if action == "update" else None)
        await interaction.response.send_modal(modal)
        await modal.wait()

        if not modal.interaction or not modal.success:
            return None

        return modal

    async def get_majors(
        self, interaction: discord.Interaction, user: User | None
    ) -> list[str]:
        """Get selected majors from major view.

        Args:
            msg: The message to update
            user: The existing user if updating

        Returns:
            List of selected majors
        """

        major_view = MajorView(
            self.major_list, current_majors=user.profile.major if user else None
        )

        msg = await interaction.followup.send(
            content="Select your major(s):",
            view=major_view,
            ephemeral=True,
            wait=True,
        )

        await major_view.wait()

        print(major_view.selected_majors)

        return major_view.selected_majors, msg

    async def verify_email(
        self, msg: discord.Message, new_email: str, user: User | None
    ) -> bool:
        """Verify user's email if needed.

        Args:
            msg: The message to update
            new_email: The email to verify
            user: The existing user if updating

        Returns:
            True if verification successful or not needed, False otherwise
        """
        if user and new_email == user.profile.school_email:
            return True

        if not new_email.endswith("edu"):
            await msg.edit(content="Invalid School email!", view=None)
            return False

        if not self.email_verifier.send_verification_email(
            msg.interaction.user.id, new_email
        ):
            await msg.edit(
                content="Failed to send verification email. Please try again.",
                view=None,
            )
            return False

        verify_view = EmailVerificationView()
        await msg.edit(
            content="Please check your email for a verification code, then click the button below to verify:",
            view=verify_view,
        )

        submitted_code = await verify_view.wait_for_verification(timeout=300.0)
        if not submitted_code:
            await msg.edit(
                content="Verification timed out. Please try again.", view=None
            )
            return False

        if not self.email_verifier.verify_code(msg.interaction.user.id, submitted_code):
            await msg.edit(
                content="Invalid verification code. Please try again.", view=None
            )
            return False

        return True

    async def handle_profile(
        self, interaction: discord.Interaction, action: str
    ) -> None:
        """Handle profile creation and updates.

        Args:
            interaction: The Discord interaction
            action: The action to perform (create/update)
        """
        user = db.get_document(User, interaction.user.id)
        self.logger.info(
            f"Profile {action} requested by {interaction.user} (ID: {interaction.user.id})"
        )

        # Check if user exists for the given action
        if action == "create" and user:
            self.logger.warning(
                f"User {interaction.user} attempted to create duplicate profile"
            )
            await interaction.response.send_message(
                "You already have a profile. Use /profile update to modify it.",
                ephemeral=True,
            )
            return
        elif action == "update" and not user:
            self.logger.warning(
                f"User {interaction.user} attempted to update non-existent profile"
            )
            await interaction.response.send_message(
                "You don't have a profile yet! Use /profile create first.",
                ephemeral=True,
            )
            return

        # Get profile data from modal
        modal = await self.get_profile_data(interaction, action, user)
        if not modal:
            self.logger.info(f"Profile {action} cancelled by {interaction.user}")
            return

        # Get major selection
        selected_majors, msg = await self.get_majors(modal.interaction, user)

        # Verify email if needed
        new_email = modal.children[4].value
        if not await self.verify_email(msg, new_email, user):
            return

        # Create or update user profile
        profile_data = {
            "name": UserName(
                first=modal.children[0].value, last=modal.children[1].value
            ),
            "major": selected_majors,
            "graduation_year": modal.children[2].value,
            "school_email": modal.children[4].value,
            "student_id": modal.children[3].value,
        }

        if action == "create":
            new_user = User(
                _id=interaction.user.id, profile=UserProfile(**profile_data)
            )
            db.add_document(new_user)
            user = new_user
            self.logger.info(f"Created new profile for {interaction.user}")
        else:
            updates = {f"profile__{k}": v for k, v in profile_data.items()}
            db.update_document(user, updates)
            user = db.get_document(User, interaction.user.id)
            self.logger.info(f"Updated profile for {interaction.user}")

        # Show the profile using followup
        await self.show_profile_embed(msg, user)

    async def show_profile_embed(
        self,
        message_or_interaction: Union[discord.Message, discord.Interaction],
        user: User,
    ) -> None:
        """Display a user's profile in an embed.

        Args:
            message_or_interaction: Either a Message or Interaction to respond to
            user: The user profile to display

        #TODO: Add profile customization options
        #TODO: Add profile badges/achievements
        """
        # Determine if we're using a Message or Interaction

        is_message = isinstance(message_or_interaction, discord.Message)

        embed = discord.Embed(
            title=f"{user.profile.name.first}'s Profile",
            color=discord.Color.purple(),
        )

        # Get the avatar URL differently based on the type
        avatar_url: str
        if isinstance(message_or_interaction, discord.Message):
            meta = message_or_interaction.interaction_metadata
            avatar_url = (
                meta.user.display_avatar.url
                if meta
                else message_or_interaction.author.display_avatar.url
            )
        else:
            avatar_url = message_or_interaction.user.display_avatar.url
        embed.set_thumbnail(url=avatar_url)
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

        # Use followup instead of edit_original_response
        # Send differently based on the type
        if is_message:
            await message_or_interaction.edit(content=None, embed=embed, view=None)
        else:
            await message_or_interaction.followup.send(embed=embed, ephemeral=True)

    async def show_profile(self, interaction: discord.Interaction) -> None:
        """Display the user's profile.

        Args:
            interaction: The Discord interaction
        """
        user = db.get_document(User, interaction.user.id)
        if not user:
            await interaction.edit_original_response(
                content="You don't have a profile yet! Use /profile create first."
            )
            return

        await self.show_profile_embed(interaction, user)

    async def delete_profile(self, interaction: discord.Interaction) -> None:
        """Delete the user's profile with confirmation.

        Args:
            interaction: The Discord interaction

        #! Note: This action is irreversible
        #TODO: Add profile backup before deletion
        """
        user = db.get_document(User, interaction.user.id)
        self.logger.info(f"Profile deletion requested by {interaction.user}")

        if not user:
            self.logger.warning(
                f"User {interaction.user} attempted to delete non-existent profile"
            )
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


async def setup(bot: commands.Bot) -> None:
    """Set up the Profile cog.

    Args:
        bot: The Discord bot instance
    """
    await bot.add_cog(ProfileCog(bot))

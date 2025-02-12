"""Profile management cog for handling user profiles."""

import json
import logging
from typing import Union, Dict
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

from config import settings
from backend.db.database import Database as db
from backend.db.documents.user import User, UserProfile, UserName
from frontend.interactions.bases.view_bases import ConfirmDeleteView
from frontend.interactions.bases.modal_base import DynamicModalView
from frontend.interactions.bases.dropdown_base import DynamicDropdownView
from .profile_handlers import EmailVerifier


class ProfileCog(commands.Cog):
    """Profile management cog for handling user profiles."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.logger = logging.getLogger(
            f"discord.cog.{self.__class__.__name__.lower()}"
        )
        self.major_list = self._load_major_list()
        self.email_verifier = EmailVerifier()
        self.config = self._load_config()

    def _load_config(self) -> dict:
        """Load profile configurations from JSON"""
        config_path = Path(__file__).parent / "profile_config.json"
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Failed to load profile config: {e}")
            return {}

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

    def _prepare_major_config(self) -> dict:
        """Prepare major dropdown config with current major list"""
        config = self.config["major_dropdown"].copy()
        config["dropdowns"][0]["selections"] = [
            {"label": major, "value": major} for major in self.major_list
        ]
        return config

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
    ) -> tuple[Dict[str, str] | None, discord.Message | None]:
        """Get profile data using modal base"""
        modal_view = DynamicModalView(**self.config["profile_modal"])

        # Pre-fill values for updates
        if action == "update" and user:
            modal_view._modal.children[0].default = user.profile.name.first
            modal_view._modal.children[1].default = user.profile.name.last
            modal_view._modal.children[2].default = user.profile.student_id
            modal_view._modal.children[3].default = user.profile.school_email
            modal_view._modal.children[4].default = user.profile.graduation_year

        return await modal_view.initiate_from_interaction(interaction)

    async def get_majors(
        self, message: discord.Message, user: User | None
    ) -> tuple[list[str], discord.Message]:
        """Get selected majors using dropdown base"""
        config = self._prepare_major_config()
        view = DynamicDropdownView(**config)

        values, message = await view.initiate_from_message(
            message, "Select your major(s):"
        )

        return values["major_selector"] if values else ["Not Set"], message

    async def verify_email(
        self, message: discord.Message, new_email: str, user: User | None
    ) -> bool:
        """Verify user's email using modal base"""
        if user and new_email == user.profile.school_email:
            return True

        if not new_email.endswith("edu"):
            await message.edit(content="Invalid School email!")
            return False

        if not self.email_verifier.send_verification_email(
            message.author.id, new_email
        ):
            await message.edit(content="Failed to send verification email.")
            return False

        verify_view = DynamicModalView(**self.config["verify_modal"])
        values, _ = await verify_view.initiate_from_message(
            message, "Please check your email for a verification code."
        )

        if not values:
            return False

        return self.email_verifier.verify_code(
            message.author.id, values["verification_code"]
        )

    async def handle_profile(
        self, interaction: discord.Interaction, action: str
    ) -> None:
        """Handle profile creation and updates."""
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

        # Get profile data directly from modal and get first message
        profile_data, message = await self.get_profile_data(interaction, action, user)
        if not profile_data or not message:
            self.logger.info(f"Profile {action} cancelled by {interaction.user}")
            return

        # Get major selection with dropdown using previous message
        selected_majors, message = await self.get_majors(message, user)

        # Verify email if needed using previous message
        if not await self.verify_email(message, profile_data["school_email"], user):
            return

        # Create user profile data
        profile_data = {
            "name": UserName(
                first=profile_data["first_name"], last=profile_data["last_name"]
            ),
            "major": selected_majors,
            "graduation_year": profile_data["graduation_year"],
            "school_email": profile_data["school_email"],
            "student_id": profile_data["student_id"],
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

        # Show the profile using the final message
        await self.show_profile_embed(message, user)

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

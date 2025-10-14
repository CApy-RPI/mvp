"""Profile management cog for handling user profiles."""

import logging
import re
import time
from pathlib import Path
from typing import Any, cast

import discord
from backend.db.database import Database
from backend.db.documents.user import User, UserName, UserProfile
from discord import app_commands
from discord.ext import commands
from frontend.interactions.bases.button_base import ConfirmDeleteView
from frontend.interactions.bases.dropdown_base import DynamicDropdownView
from frontend.interactions.bases.modal_base import (
    ButtonDynamicModalView,
    DynamicModalView,
)

from config import settings

from .major_handler import MajorHandler
from .profile_config import PROFILE_CONFIG
from .profile_handlers import EmailVerifier


def out_of_bounds_exclusive(n: str, lower, upper):
    """Returns whether n is both a valid digit and out of the given bounds."""
    if not n.isdigit():
        return False
    return not lower < int(n) < upper


class TryAgainView(discord.ui.View):
    def __init__(self, parent_cog, action):
        super().__init__(timeout=60)
        self.parent_cog = parent_cog
        self.action = action

    @discord.ui.button(label="Try Again", style=discord.ButtonStyle.primary)
    async def retry_button(self, interaction: discord.Interaction, _: discord.ui.Button[Any]):
        await self.parent_cog.handle_profile(interaction, self.action)
        self.stop()


class ProfileCog(commands.Cog):
    """Profile management cog for handling user profiles."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.logger = logging.getLogger(f"discord.cog.{self.__class__.__name__.lower()}")
        self.major_list = self._load_major_list()
        self.email_verifier = EmailVerifier()
        self.config = PROFILE_CONFIG
        self.major_handler = MajorHandler(self.major_list)

    def _load_major_list(self) -> list[str]:
        """Load the list of available majors from file."""
        try:
            with Path(settings.MAJORS_PATH).open(encoding="utf-8") as f:
                majors = [line.strip() for line in f.readlines() if line.strip()]
                self.logger.info(f"Loaded {len(majors)} majors from file")
                if not majors:
                    self.logger.warning("majors.txt is empty")
                return majors
        except FileNotFoundError:
            self.logger.error(f"majors.txt not found at {settings.MAJORS_PATH}")
            return ["Not Set"]
        except Exception as e:
            self.logger.error(f"Error loading majors from {settings.MAJORS_PATH}: {e}")
            return ["Not Set"]

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
    ) -> tuple[dict[str, str] | None, discord.Message | None]:
        """Get profile data using modal base"""
        modal_view = DynamicModalView(**self.config["profile_modal"])

        # Pre-fill values for updates
        if action == "update" and user:
            # Combine first and last name into preferred name
            preferred_name = f"{user.profile.name.first} {user.profile.name.last}".strip()
            modal_view._modal.children[0].default = preferred_name
            modal_view._modal.children[1].default = user.profile.student_id
            modal_view._modal.children[2].default = user.profile.school_email
            modal_view._modal.children[3].default = user.profile.graduation_year
            # Pre-fill majors field with existing majors string
            modal_view._modal.children[4].default = user.profile.major

        result = await modal_view.initiate_from_interaction(interaction)
        return cast(tuple[dict[str, str] | None, discord.Message | None], result)

    async def get_majors(
        self, message: discord.Message, _user: User | None
    ) -> tuple[list[str] | None, discord.Message]:
        """Get selected majors using dropdown base"""
        config = self.major_handler.get_dropdown_config(self.config["major_dropdown"])
        view = DynamicDropdownView(**config)

        values, message = await view.initiate_from_message(message, self.major_handler.get_help_text())
        self.logger.debug(f"Dropdown values: {values}")

        if not values:
            return None, message

        # Combine selections from all dropdowns
        selected = []
        for dropdown_id in values:
            selected.extend(values[dropdown_id])

        # The global limit is now enforced at the dropdown level
        return selected, message

    def process_majors_from_text(self, majors_text: str) -> list[str]:
        """Process majors from comma-separated text input"""
        self.logger.debug(f"Processing majors text: '{majors_text}' (stripped: '{majors_text.strip()}')")

        if not majors_text.strip():
            self.logger.debug("Majors text is empty after stripping")
            return []

        # Split by commas and clean up each major
        majors = [major.strip() for major in majors_text.split(",")]
        self.logger.debug(f"Split majors: {majors}")

        # Remove empty strings
        majors = [major for major in majors if major]
        self.logger.debug(f"Final majors after filtering: {majors}")

        return majors

    async def verify_email(self, message: discord.Message, new_email: str, user: User | None) -> bool:
        """Verify user's email using button modal base"""
        if user and new_email == user.profile.school_email:
            return True

        if not self.email_verifier.send_verification_email(message.author.id, new_email):
            await message.edit(content="Failed to send verification email.")
            return False

        verify_view = ButtonDynamicModalView(**self.config["verify_modal"])
        values, _ = await verify_view.initiate_from_message(message)

        if not values:
            return False
        return self.email_verifier.verify_code(message.author.id, values["verification_code"])

    async def send_verification_code(self, message: discord.Message, new_email: str, user: User | None) -> bool:
        """Send verification code without prompting for input yet."""
        if user and new_email == user.profile.school_email:
            return True

        if not self.email_verifier.send_verification_email(message.author.id, new_email):
            await message.edit(content="Failed to send verification email.")
            return False

        # Inform user that verification code has been sent
        await message.edit(content=("Verification code sent to your email. Please check your inbox."))
        return True

    async def prompt_and_verify_code(self, message: discord.Message) -> bool:
        """Prompt user for verification code and validate it with retries."""
        max_attempts = 5
        attempt = 0
        while attempt < max_attempts:
            verify_view = ButtonDynamicModalView(**self.config["verify_modal"])
            values, _ = await verify_view.initiate_from_message(message)

            # If user closes/cancels the modal, abort verification entirely
            if not values:
                return False

            if self.email_verifier.verify_code(message.author.id, values["verification_code"]):
                return True

            attempt += 1
            attempts_left = max_attempts - attempt
            if attempts_left > 0:
                await message.edit(content=f"Incorrect code. Try again. Attempts left: {attempts_left}")
            else:
                await message.edit(content="Verification failed after 5 attempts. Please start over.")
        return False

    async def handle_profile(self, interaction: discord.Interaction, action: str) -> None:
        """Handle profile creation and updates."""
        user = Database.get_document(User, interaction.user.id)
        self.logger.info(f"Profile {action} requested by {interaction.user} (ID: {interaction.user.id})")

        if not await self._validate_action(interaction, action, user):
            return

        prepared = await self._prepare_profile_data(interaction, action, user)
        if not prepared:
            return
        profile_data, message = prepared

        # Process majors from form input
        majors_text = profile_data.get("major(s)", "").strip()
        processed_majors = self.process_majors_from_text(majors_text)

        # Convert processed majors list back to string for storage
        majors_string = ", ".join(processed_majors) if processed_majors else ""

        self.logger.info(f"Processed majors from '{majors_text}' -> {processed_majors} -> '{majors_string}'")

        # Process email verification after form submission
        if not await self._process_email_verification(message, user, profile_data):
            return

        await self._save_profile(
            interaction,
            action,
            profile_data,
            {"majors_string": majors_string, "user": user, "message": message},
        )

    async def _prepare_profile_data(
        self, interaction: discord.Interaction, action: str, user: User | None
    ) -> tuple[dict[str, str], discord.Message] | None:
        """Collect and validate profile data, returning payload and message or None to abort."""
        profile_data, message = await self.get_profile_data(interaction, action, user)
        if not profile_data or not message:
            self.logger.info(f"Profile {action} cancelled by {interaction.user}")
            return None
        if not await self._validate_profile_data(profile_data, message, action):
            return None
        return profile_data, message

    async def _process_email_verification(
        self, message: discord.Message, user: User | None, profile_data: dict[str, str]
    ) -> bool:
        """Handle email verification flow, returning True if successful or False to abort."""
        needs_verification = not (user and profile_data["school_email"] == user.profile.school_email)

        if needs_verification:
            if not await self.send_verification_code(message, profile_data["school_email"], user):
                return False

            if not await self.prompt_and_verify_code(message):
                return False

        return True

    async def _validate_action(self, interaction, action, user) -> bool:
        if action == "create" and user:
            self.logger.warning(f"User {interaction.user} attempted to create duplicate profile")
            await interaction.response.send_message(
                "You already have a profile. Use /profile update to modify it.",
                ephemeral=True,
            )
            return False
        elif action == "update" and not user:
            self.logger.warning(f"User {interaction.user} attempted to update non-existent profile")
            await interaction.response.send_message(
                "You don't have a profile yet! Use /profile create first.",
                ephemeral=True,
            )
            return False
        return True

    async def _validate_profile_data(self, profile_data, message, action) -> bool:
        content = ""
        trycheck = False

        # Check if preferred name contains only letters and spaces
        if not profile_data["preferred_name"].strip():
            content += "Preferred name cannot be empty.\n"
            trycheck = True
        elif not re.match(r"[a-zA-Z\s]+$", profile_data["preferred_name"].strip()):
            content += "Names can only contain letters and spaces.\n"
            trycheck = True
        if not (profile_data["graduation_year"].isdigit()):
            content += "Graduation year must be a number.\n"
            trycheck = True
        if not (profile_data["student_id"].isdigit()):
            content += "Student ID must be a number.\n"
            trycheck = True
        if not profile_data["school_email"].endswith("edu"):
            content += "School email must end with 'edu'.\n"
            trycheck = True

        # Validate majors field
        majors_text = profile_data.get("major(s)", "").strip()
        if not majors_text:
            content += "At least one major must be specified.\n"
            trycheck = True
        else:
            # Check that processing majors results in at least one valid major
            processed_majors = self.process_majors_from_text(majors_text)
            if not processed_majors:
                content += "Please enter valid major(s) separated by commas.\n"
                trycheck = True

        grad_year_lower_bound = 1899
        grad_year_upper_bound = 2100
        if out_of_bounds_exclusive(profile_data["graduation_year"], grad_year_lower_bound, grad_year_upper_bound):
            content += "Graduation year outside of acceptable bounds.\n"
            trycheck = True

        if trycheck:
            view = TryAgainView(self, action)
            await message.edit(content=content, view=view)
            return False

        return True

    async def _get_valid_majors(self, message, user) -> list[str] | None:
        while True:
            try:
                selected_majors, message = await self.get_majors(message, user)

                # If user canceled, return None to abort the entire process
                if selected_majors is None:
                    return None

                # If majors were selected, return them
                if selected_majors and selected_majors != ["Not Set"]:
                    return selected_majors

                await message.edit(content="⚠️ Please select 1 or 2 majors.")
                time.sleep(1)

            except Exception as e:
                await message.edit(content=str(e))
                time.sleep(5)

    def get_majors_from_profile_data(self, profile_data: dict[str, str]) -> list[str]:
        """Extract and validate majors from profile data text input"""
        majors_text = profile_data.get("major(s)", "")
        self.logger.debug(f"Raw majors text: '{majors_text}'")
        processed_majors = self.process_majors_from_text(majors_text)
        self.logger.debug(f"Processed majors result: {processed_majors}")
        return processed_majors

    async def _save_profile(
        self,
        interaction: discord.Interaction,
        action: str,
        profile_data: dict[str, str],
        context: dict[str, Any],
    ) -> None:
        """Save the user profile to the database."""
        self.logger.info(f"Starting to save profile for {action}")
        majors_string = context["majors_string"]
        user = context["user"]

        # Split preferred name into first and last name
        name_parts = profile_data["preferred_name"].strip().split()
        if len(name_parts) == 1:
            first_name = name_parts[0]
            last_name = ""
        else:
            first_name = name_parts[0]
            last_name = " ".join(name_parts[1:])  # Handle multiple middle/last names

        profile_data_dict = {
            "name": UserName(first=first_name, last=last_name),
            "major": majors_string,
            "graduation_year": int(profile_data["graduation_year"]),
            "school_email": profile_data["school_email"],
            "student_id": int(profile_data["student_id"]),
        }

        try:
            if action == "create":
                new_user = User(_id=interaction.user.id, profile=UserProfile(**profile_data_dict))
                Database.add_document(new_user)
                user = new_user
                self.logger.info(f"Successfully created new profile for {interaction.user}")
            else:
                updates = {f"profile__{k}": v for k, v in profile_data_dict.items()}
                Database.update_document(user, updates)
                user = Database.get_document(User, interaction.user.id)
                self.logger.info(f"Successfully updated profile for {interaction.user}")

            # Show the profile using the original interaction to get user's avatar
            await self.show_profile_embed(interaction, user)
        except Exception as e:
            self.logger.error(f"Failed to save profile: {e}")
            await interaction.followup.send(
                "An error occurred while saving your profile. Please try again.",
                ephemeral=True,
            )

    async def show_profile_embed(
        self,
        message_or_interaction: discord.Message | discord.Interaction,
        user: User,
    ) -> None:
        """Display a user's profile in an embed."""
        is_interaction = isinstance(message_or_interaction, discord.Interaction)

        embed = discord.Embed(
            title=f"{user.profile.name.first}'s Profile",
            color=discord.Color.purple(),
        )

        avatar_url: str
        if is_interaction:
            interaction = cast(discord.Interaction, message_or_interaction)
            avatar_url = interaction.user.display_avatar.url
        else:
            message = cast(discord.Message, message_or_interaction)
            avatar_url = message.author.display_avatar.url

        embed.set_thumbnail(url=avatar_url)
        embed.add_field(name="First Name", value=user.profile.name.first, inline=True)
        embed.add_field(name="Last Name", value=user.profile.name.last, inline=True)
        embed.add_field(name="Major", value=user.profile.major, inline=True)
        embed.add_field(name="Graduation Year", value=user.profile.graduation_year, inline=True)
        embed.add_field(name="School Email", value=user.profile.school_email, inline=True)
        embed.add_field(name="Student ID", value=user.profile.student_id, inline=True)

        if is_interaction:
            interaction = cast(discord.Interaction, message_or_interaction)
            if interaction.response.is_done():
                try:
                    await interaction.edit_original_response(embed=embed)
                except Exception:
                    # If there's no original message (e.g., modal used), send a followup instead
                    await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            message = cast(discord.Message, message_or_interaction)
            await message.edit(content=None, embed=embed, view=None)

    async def show_profile(self, interaction: discord.Interaction) -> None:
        """Display the user's profile.

        Args:
            interaction: The Discord interaction
        """
        user = Database.get_document(User, interaction.user.id)
        if not user:
            await interaction.edit_original_response(content="You don't have a profile yet! Use /profile create first.")
            return

        await self.show_profile_embed(interaction, user)

    async def delete_profile(self, interaction: discord.Interaction) -> None:
        """Delete the user's profile with confirmation.

        Args:
            interaction: The Discord interaction

        #! Note: This action is irreversible
        #TODO: Add profile backup before deletion
        """
        user = Database.get_document(User, interaction.user.id)
        self.logger.info(f"Profile deletion requested by {interaction.user}")

        if not user:
            self.logger.warning(f"User {interaction.user} attempted to delete non-existent profile")
            await interaction.edit_original_response(content="You don't have a profile to delete.")
            return

        view = ConfirmDeleteView()
        await interaction.edit_original_response(
            content="⚠️ Are you sure you want to delete your profile? This action cannot be undone.",
            view=view,
        )

        await view.wait()
        if view.value:
            Database.delete_document(user)
            await interaction.edit_original_response(content="Your profile has been deleted.", view=None)
        else:
            await interaction.edit_original_response(content="Profile deletion cancelled.", view=None)


async def setup(bot: commands.Bot) -> None:
    """Set up the Profile cog.

    Args:
        bot: The Discord bot instance
    """
    await bot.add_cog(ProfileCog(bot))

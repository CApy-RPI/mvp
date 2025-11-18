"""Profile management cog for handling user profiles."""

import asyncio
import logging
import re
from pathlib import Path
from typing import Any, cast

import discord
from backend.db.database import Database
from backend.db.documents.event import Event
from backend.db.documents.guild import Guild
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
from .profile_handlers import VERIFICATION_CODE_LENGTH, EmailVerifier

# Constants
MAX_MAJORS_ALLOWED = 2


def out_of_bounds_exclusive(n: str, lower, upper):
    """Returns whether n is both a valid digit and out of the given bounds."""
    if not n.isdigit():
        return False
    return not lower < int(n) < upper


class TryAgainView(discord.ui.View):
    def __init__(self, parent_cog, action, invalid_data=None):
        super().__init__(timeout=60)
        self.parent_cog = parent_cog
        self.action = action
        self.invalid_data = invalid_data or {}

    @discord.ui.button(label="Try Again", style=discord.ButtonStyle.primary)
    async def retry_button(self, interaction: discord.Interaction, _: discord.ui.Button[Any]):
        # Acknowledge the interaction to avoid timeouts/jitter
        await interaction.response.defer(ephemeral=True)
        await self.parent_cog.handle_profile(interaction, self.action, retry_data=self.invalid_data)
        self.stop()


class SuggestionView(discord.ui.View):
    """View for confirming suggested major corrections."""

    def __init__(self, parent_cog, action, profile_data, suggestions, validated_majors):
        super().__init__(timeout=60)
        self.parent_cog = parent_cog
        self.action = action
        self.profile_data = profile_data
        self.suggestions = suggestions
        self.validated_majors = validated_majors
        self.accepted = False

    @discord.ui.button(label="Accept Suggestions", style=discord.ButtonStyle.success)
    async def accept_button(self, interaction: discord.Interaction, _button: discord.ui.Button[Any]):
        """Accept the suggested corrections and continue with profile."""
        # Acknowledge the interaction immediately to prevent timeout
        await interaction.response.defer(ephemeral=True)
        self.accepted = True
        # Apply the suggestions to validated_majors
        for _original, suggested in self.suggestions.items():
            self.validated_majors.append(suggested)
        self.stop()

    @discord.ui.button(label="Try Again", style=discord.ButtonStyle.primary)
    async def retry_button(self, interaction: discord.Interaction, _button: discord.ui.Button[Any]):
        """Reject suggestions and return to form with all data except majors."""
        # Acknowledge the interaction to avoid timeouts/jitter
        await interaction.response.defer(ephemeral=True)
        self.accepted = False
        # Keep all profile data EXCEPT the major field - user needs to re-enter majors
        retry_data = {k: v for k, v in self.profile_data.items() if k != "major(s)"}
        await self.parent_cog.handle_profile(interaction, self.action, retry_data=retry_data)
        self.stop()


async def delete_profile_from_events(user):
    if not hasattr(user, "events"):
        return

    for event_id in user.events:
        event = Database.get_document(Event, event_id)
        # TODO remove the frontend RSVP reactions of the deleted user
        if event:
            # Remove from RSVPs
            if user.id in event.yes_users:
                event.yes_users.remove(user.id)
                event.details.reactions.modify("yes", -1)
            if user.id in event.no_users:
                event.no_users.remove(user.id)
                event.details.reactions.modify("no", -1)
            if user.id in event.maybe_users:
                event.maybe_users.remove(user.id)
                event.details.reactions.modify("maybe", -1)
            event.save()


async def delete_profile_from_guilds(user):
    if not hasattr(user, "guilds"):
        return

    for guild_id in user.guilds:
        guild = Database.get_document(Guild, guild_id)
        if guild and user.id in guild.users:
            guild.users.remove(user.id)
            guild.save()


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
        self,
        interaction: discord.Interaction,
        action: str,
        user: User | None,
        retry_data: dict[str, str] | None = None,
    ) -> tuple[dict[str, str] | None, discord.Message | None]:
        """Get profile data using modal base"""
        modal_view = DynamicModalView(**self.config["profile_modal"])

        # Pre-fill values for retries (highest priority)
        if retry_data:
            modal_view._modal.children[0].default = retry_data.get("preferred_name", "")
            student_id_value = retry_data.get("student_id", "")
            modal_view._modal.children[1].default = student_id_value if student_id_value else ""
            modal_view._modal.children[2].default = retry_data.get("school_email", "")
            graduation_year_value = retry_data.get("graduation_year", "")
            modal_view._modal.children[3].default = graduation_year_value if graduation_year_value else ""
            modal_view._modal.children[4].default = retry_data.get("major(s)", "")
        # Pre-fill values for updates
        elif action == "update" and user:
            # Combine first and last name into preferred name
            preferred_name = f"{user.profile.name.first} {user.profile.name.last}".strip()
            modal_view._modal.children[0].default = preferred_name
            modal_view._modal.children[1].default = str(user.profile.student_id)
            modal_view._modal.children[2].default = user.profile.school_email
            modal_view._modal.children[3].default = str(user.profile.graduation_year)
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
        # UI-side validation: must be exactly 6 digits (allow spaces around/in between)
        raw_code = values.get("verification_code", "")
        normalized = raw_code.strip().replace(" ", "")
        if not (len(normalized) == VERIFICATION_CODE_LENGTH and normalized.isdigit()):
            await message.edit(content="Please enter a valid 6-digit numeric code.")
            return False
        return self.email_verifier.verify_code(message.author.id, normalized)

    async def send_verification_code(
        self,
        message: discord.Message,
        new_email: str,
        user: User | None,
        _interaction: discord.Interaction | None = None,
    ) -> bool:
        """Send verification code without prompting for input yet."""
        if user and new_email == user.profile.school_email:
            return True

        if not self.email_verifier.send_verification_email(message.author.id, new_email):
            await message.edit(content="Failed to send verification email.")
            return False

        # Do not send a separate notice here; the next prompt already states
        # that a verification code has been sent. Keeping this silent avoids duplication.
        return True

    async def prompt_and_verify_code(self, message: discord.Message) -> bool:
        """Prompt user for verification code and validate it with retries."""
        max_attempts = 5
        attempt = 0
        error_message = ""  # Track error message to display above verification prompt

        while attempt < max_attempts:
            # Build the prompt with error message if there is one
            base_prompt = "A verification code has been sent to your email.\nClick below when ready to verify:"
            prompt = f"{error_message}\n\n{base_prompt}" if error_message else base_prompt

            verify_view = ButtonDynamicModalView(**self.config["verify_modal"])
            values, _ = await verify_view.initiate_from_message(message, prompt=prompt)

            # If user closes/cancels the modal, abort verification entirely
            if not values:
                return False

            # UI-side validation before verifying: enforce 6 digits
            raw_code = values.get("verification_code", "")
            normalized = raw_code.strip().replace(" ", "")
            if not (len(normalized) == VERIFICATION_CODE_LENGTH and normalized.isdigit()):
                error_message = "❌ Please enter a valid 6-digit numeric code."
                # Do not count this as an attempt; let user re-enter
                continue

            if self.email_verifier.verify_code(message.author.id, normalized):
                return True

            attempt += 1
            attempts_left = max_attempts - attempt
            if attempts_left > 0:
                error_message = f"❌ Incorrect code. **Attempts remaining: {attempts_left}**"
            else:
                await message.edit(
                    content="❌ Verification failed after 5 attempts. Please start over.",
                    view=None,
                )
                return False
        return False

    async def handle_profile(
        self,
        interaction: discord.Interaction,
        action: str,
        retry_data: dict[str, str] | None = None,
    ) -> None:
        """Handle profile creation and updates."""
        user = Database.get_document(User, interaction.user.id)
        self.logger.info(f"Profile {action} requested by {interaction.user} (ID: {interaction.user.id})")

        if not await self._validate_action(interaction, action, user):
            return

        prepared = await self._prepare_profile_data(interaction, action, user, retry_data)
        if not prepared:
            return
        profile_data, message = prepared

        # Process and validate majors
        majors_result = await self._process_and_validate_majors(profile_data, message, action, interaction)
        if majors_result is None:
            return  # Validation failed or user needs to retry
        majors_string = majors_result

        # Process email verification after form submission
        if not await self._process_email_verification(message, user, profile_data):
            return

        # First, clear the message to show success
        await message.edit(content="✅ Form submitted successfully!", embed=None, view=None)
        # Give a brief moment before replacing with the profile embed
        await asyncio.sleep(1)

        await self._save_profile(
            interaction,
            action,
            profile_data,
            {
                "majors_string": majors_string,
                "user": user,
                "message": message,
                "interaction": interaction,
            },
        )

    async def _process_and_validate_majors(
        self,
        profile_data: dict[str, str],
        message: discord.Message,
        action: str,
        interaction: discord.Interaction,
    ) -> str | None:
        """Process and validate majors, handling auto-corrections and suggestions.

        Returns the validated majors string if successful, or None if validation failed.
        """
        # Process majors from form input
        majors_text = profile_data.get("major(s)", "").strip()
        processed_majors = self.process_majors_from_text(majors_text)

        # Validate and normalize majors with fuzzy matching for typos
        all_valid, validated_majors, invalid_majors, auto_corrections, suggestions = (
            self.major_handler.validate_majors_with_corrections(processed_majors)
        )

        # Use the validated majors (with correct casing from majors.txt)
        majors_string = ", ".join(validated_majors) if validated_majors else ""

        self.logger.info(
            f"Processed majors: '{majors_text}' -> {processed_majors} -> "
            f"validated: {validated_majors} -> '{majors_string}'"
        )

        # Show auto-corrections to user if any typos were auto-corrected (score >= 90%)
        if auto_corrections:
            await self._show_auto_corrections(message, auto_corrections, interaction)

        # Handle suggestions (60-90% confidence) - need user confirmation
        if suggestions:
            suggestion_result = await self._handle_suggestions(
                message, action, profile_data, suggestions, validated_majors
            )
            if suggestion_result is None:
                return None  # User clicked Try Again
            majors_string = suggestion_result

        # Show error if any majors were invalid
        if invalid_majors:
            error_msg = self.major_handler.get_validation_error_message(invalid_majors)
            error_msg += "\nPlease check your spelling and try again."
            await message.edit(content=error_msg)
            return None

        return majors_string

    async def _show_auto_corrections(
        self,
        message: discord.Message,
        auto_corrections: dict[str, str],
        interaction: discord.Interaction,
    ) -> None:
        """Display auto-corrected typos to the user."""
        correction_msg = "✅ **Auto-corrected typos:**\n"
        for original, corrected in auto_corrections.items():
            correction_msg += f"  • '{original}' → '{corrected}'\n"
        await message.edit(content=correction_msg)
        # Keep the informational message visible and ephemeral
        await interaction.followup.send("Continuing with profile...", ephemeral=True)
        # Small pause so users can read the info before the next UI step
        await asyncio.sleep(1)

    async def _handle_suggestions(
        self,
        message: discord.Message,
        action: str,
        profile_data: dict[str, str],
        suggestions: dict[str, str],
        validated_majors: list[str],
    ) -> str | None:
        """Handle major suggestions that need user confirmation.

        Returns the validated majors string if accepted, or None if user wants to retry.
        """
        suggestion_msg = "❓ **Did you mean:**\n"
        for original, suggested in suggestions.items():
            suggestion_msg += f"  • '{original}' → '{suggested}'?\n"
        suggestion_msg += "\nPlease choose an option below:"

        # Create view with Accept and Try Again buttons
        view = SuggestionView(self, action, profile_data, suggestions, validated_majors)
        await message.edit(content=suggestion_msg, view=view)

        # Wait for user to click a button
        await view.wait()

        # If user accepted suggestions, continue with the updated validated_majors
        if view.accepted:
            # Update majors_string with the newly added suggestions
            majors_string = ", ".join(view.validated_majors) if view.validated_majors else ""
            self.logger.info(f"User accepted suggestions. Final majors: {view.validated_majors}")
            # Continue with profile processing
            await message.edit(
                content="✅ Suggestions accepted. Continuing with profile...",
                view=None,
            )
            # Brief pause so the message is readable before the next step replaces it
            await asyncio.sleep(1)
            return majors_string

        # User clicked Try Again - already handled by the button callback
        return None

    async def _prepare_profile_data(
        self,
        interaction: discord.Interaction,
        action: str,
        user: User | None,
        retry_data: dict[str, str] | None = None,
    ) -> tuple[dict[str, str], discord.Message] | None:
        """Collect and validate profile data, returning payload and message or None to abort."""
        profile_data, message = await self.get_profile_data(interaction, action, user, retry_data)
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
            if not await self.send_verification_code(
                message,
                profile_data["school_email"],
                user,
            ):
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

    def _validate_name(self, profile_data: dict[str, str]) -> tuple[bool, str]:
        """Validate preferred name field."""
        name = profile_data["preferred_name"].strip()
        if not name:
            return False, "Preferred name cannot be empty.\n"
        if not re.match(r"[a-zA-Z\s]+$", name):
            return False, "Names can only contain letters and spaces.\n"
        return True, ""

    def _validate_graduation_year(self, profile_data: dict[str, str]) -> tuple[bool, str]:
        """Validate graduation year field."""
        grad_year = profile_data["graduation_year"]
        if not grad_year.isdigit():
            return False, "Graduation year must be a number.\n"

        grad_year_lower_bound = 1899
        grad_year_upper_bound = 2100
        if out_of_bounds_exclusive(grad_year, grad_year_lower_bound, grad_year_upper_bound):
            return False, "Graduation year outside of acceptable bounds.\n"
        return True, ""

    def _validate_student_id(self, profile_data: dict[str, str]) -> tuple[bool, str]:
        """Validate student ID field."""
        if not profile_data["student_id"].isdigit():
            return False, "Student ID must be a number.\n"
        return True, ""

    def _validate_email(self, profile_data: dict[str, str]) -> tuple[bool, str]:
        """Validate school email field."""
        if not profile_data["school_email"].endswith("edu"):
            return False, "School email must end with 'edu'.\n"
        return True, ""

    def _validate_majors_field(self, profile_data: dict[str, str]) -> tuple[bool, str]:
        """Validate majors field has content (actual validation happens later with fuzzy matching)."""
        majors_text = profile_data.get("major(s)", "").strip()
        if not majors_text:
            return False, "At least one major must be specified.\n"

        processed_majors = self.process_majors_from_text(majors_text)
        if not processed_majors:
            return False, "Please enter valid major(s) separated by commas.\n"

        if len(processed_majors) > MAX_MAJORS_ALLOWED:
            return False, f"You can only specify up to {MAX_MAJORS_ALLOWED} majors.\n"

        # Don't validate actual major names here - that happens in _process_and_validate_majors
        # with fuzzy matching and abbreviation support
        return True, ""

    def _prepare_retry_data(self, profile_data: dict[str, str]) -> dict[str, str]:
        """Prepare retry data by clearing invalid fields."""
        retry_data = profile_data.copy()

        # Clear invalid name
        name_valid, _ = self._validate_name(profile_data)
        if not name_valid:
            retry_data["preferred_name"] = ""

        # Clear invalid graduation year
        grad_year_valid, _ = self._validate_graduation_year(profile_data)
        if not grad_year_valid:
            retry_data["graduation_year"] = ""

        # Clear invalid student ID
        student_id_valid, _ = self._validate_student_id(profile_data)
        if not student_id_valid:
            retry_data["student_id"] = ""

        # Clear invalid email
        email_valid, _ = self._validate_email(profile_data)
        if not email_valid:
            retry_data["school_email"] = ""

        # Clear invalid majors
        majors_valid, _ = self._validate_majors_field(profile_data)
        if not majors_valid:
            retry_data["major(s)"] = ""

        return retry_data

    async def _validate_profile_data(self, profile_data, message, action) -> bool:
        """Validate all profile data fields."""
        content = ""
        is_valid = True

        # Validate each field
        name_valid, name_error = self._validate_name(profile_data)
        if not name_valid:
            content += name_error
            is_valid = False

        grad_year_valid, grad_year_error = self._validate_graduation_year(profile_data)
        if not grad_year_valid:
            content += grad_year_error
            is_valid = False

        student_id_valid, student_id_error = self._validate_student_id(profile_data)
        if not student_id_valid:
            content += student_id_error
            is_valid = False

        email_valid, email_error = self._validate_email(profile_data)
        if not email_valid:
            content += email_error
            is_valid = False

        majors_valid, majors_error = self._validate_majors_field(profile_data)
        if not majors_valid:
            content += majors_error
            is_valid = False

        if not is_valid:
            retry_data = self._prepare_retry_data(profile_data)
            view = TryAgainView(self, action, retry_data)
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
                await asyncio.sleep(1)

            except Exception as e:
                await message.edit(content=str(e))
                await asyncio.sleep(5)

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
        message = context["message"]
        interaction_ctx = context["interaction"]  # Get the interaction from context

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
                await self._link_user_to_guilds(interaction)
            else:
                updates = {f"profile__{k}": v for k, v in profile_data_dict.items()}
                Database.update_document(user, updates)
                user = Database.get_document(User, interaction.user.id)
                self.logger.info(f"Successfully updated profile for {interaction.user}")

            # Show the profile using the message to display after "Form submitted successfully"
            # Pass interaction to get the correct user avatar
            await self.show_profile_embed(message, user, interaction_ctx)
        except Exception as e:
            self.logger.error(f"Failed to save profile: {e}")
            await interaction.followup.send(
                "An error occurred while saving your profile. Please try again.",
                ephemeral=True,
            )

    def _get_target_guild_ids(self, interaction: discord.Interaction) -> list[int]:
        """Determine which guild IDs to assign to the user.

        Args:
            interaction: The Discord interaction

        Returns:
            List of guild IDs to assign to the user
        """
        user_id = interaction.user.id

        # If interaction is in a guild, return that guild ID
        if interaction.guild_id:
            self.logger.info(f"Profile created in guild {interaction.guild_id}")
            return [int(interaction.guild_id)]

        # If in DMs, find all mutual guilds where the bot sees the user as a member
        mutual_guild_ids = []
        for guild in self.bot.guilds:
            member = guild.get_member(user_id)
            if member and not member.bot:
                mutual_guild_ids.append(int(guild.id))
                self.logger.debug(f"Found user {user_id} in guild {guild.id} ({guild.name})")

        self.logger.info(f"Profile created in DMs, found {len(mutual_guild_ids)} mutual guilds")
        return mutual_guild_ids

    def _ensure_guild_exists(self, guild_id: int) -> Guild:
        """Ensure a Guild document exists in the database.

        Args:
            guild_id: The guild ID to ensure exists

        Returns:
            The Guild document
        """
        guild_doc = Database.get_document(Guild, guild_id)
        if not guild_doc:
            guild_doc = Guild(_id=guild_id)
            Database.add_document(guild_doc)
            self.logger.info(f"Created Guild document for {guild_id}")
        return guild_doc

    def _add_user_to_guild(self, guild_id: int, user_id: int) -> None:
        """Add a user to a guild's user list.

        Args:
            guild_id: The guild ID
            user_id: The user ID to add
        """
        try:
            guild_doc = self._ensure_guild_exists(guild_id)

            existing_users = getattr(guild_doc, "users", []) or []
            if user_id not in existing_users:
                existing_users.append(user_id)
                Database.update_document(guild_doc, {"users": sorted(existing_users)})
                self.logger.info(f"Added user {user_id} to Guild.users for {guild_id}")
            else:
                self.logger.debug(f"User {user_id} already in Guild.users for {guild_id}")
        except Exception as e:
            # Non-fatal: log and continue
            self.logger.error(f"Failed to add user {user_id} to Guild.users for {guild_id}: {e}")

    async def _link_user_to_guilds(self, interaction: discord.Interaction) -> None:
        """Link a user to their guilds after profile creation.

        This handles both server and DM initiation paths:
        - In servers: links to the current guild
        - In DMs: links to all mutual guilds where the bot sees the user

        Args:
            interaction: The Discord interaction
        """
        user_id = interaction.user.id

        try:
            # Determine which guilds to link
            target_guild_ids = self._get_target_guild_ids(interaction)

            if not target_guild_ids:
                self.logger.warning(f"No guilds found for user {user_id}")
                return

            # Update User.guilds with add-to-set semantics (no duplicates)
            for guild_id in target_guild_ids:
                try:
                    Database.bulk_update_attr(User, [user_id], "guilds", guild_id)
                    self.logger.info(f"Added guild {guild_id} to User.guilds for {user_id}")
                except Exception as e:
                    # Non-fatal: log and continue with other guilds
                    self.logger.error(f"Failed to add guild {guild_id} to User.guilds for {user_id}: {e}")

            # Ensure Guild documents exist and add user to Guild.users
            for guild_id in target_guild_ids:
                self._add_user_to_guild(guild_id, user_id)

            self.logger.info(f"Successfully linked user {user_id} to {len(target_guild_ids)} guild(s)")

        except Exception as e:
            # Non-fatal: profile is more important than guild links
            self.logger.error(f"Error linking user {user_id} to guilds: {e}", exc_info=True)

    async def show_profile_embed(
        self,
        message_or_interaction: discord.Message | discord.Interaction,
        user: User,
        user_interaction: discord.Interaction | None = None,
    ) -> None:
        """Display a user's profile in an embed.

        Args:
            message_or_interaction: The message or interaction to use for displaying
            user: The user whose profile to display
            user_interaction: Optional interaction to get the user's avatar from
        """
        is_interaction = isinstance(message_or_interaction, discord.Interaction)

        embed = discord.Embed(
            title=f"{user.profile.name.first}'s Profile",
            color=discord.Color.purple(),
        )

        avatar_url: str
        # If we have a user_interaction, use that for the avatar (handles message case)
        if user_interaction:
            avatar_url = user_interaction.user.display_avatar.url
        elif is_interaction:
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

        view = ConfirmDeleteView(timeout=60)
        await interaction.edit_original_response(
            content="⚠️ Are you sure you want to delete your profile? This action cannot be undone.",
            view=view,
        )

        # Wait for button press
        timed_out = await view.wait()

        if view.value and view.interaction:
            # Use the button interaction to update the message - this acknowledges it
            await view.interaction.response.edit_message(content="⏳ Deleting your profile...", view=None)

            # Remove user from events and guilds BEFORE deleting the user document
            await delete_profile_from_events(user)
            await delete_profile_from_guilds(user)

            # Now delete the user document
            Database.delete_document(user)

            # Show success message
            await interaction.edit_original_response(content="✅ Your profile has been deleted.", view=None)
        elif timed_out:
            await interaction.edit_original_response(content="❌ Profile deletion timed out.", view=None)
        elif view.interaction:
            # User cancelled - use button interaction to respond
            await view.interaction.response.edit_message(content="❌ Profile deletion cancelled.", view=None)
        else:
            # Fallback if no interaction (shouldn't happen)
            await interaction.edit_original_response(content="❌ Profile deletion cancelled.", view=None)


async def setup(bot: commands.Bot) -> None:
    """Set up the Profile cog.

    Args:
        bot: The Discord bot instance
    """
    await bot.add_cog(ProfileCog(bot))

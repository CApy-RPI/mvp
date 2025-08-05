"""Profile management cog for handling user profiles."""

import logging
import time
from pathlib import Path

import discord
from backend.db.database import Database
from backend.db.documents.user import User, UserName, UserProfile
from discord import app_commands
from discord.ext import commands
from frontend.interactions.bases.button_base import ConfirmDeleteView
from frontend.interactions.bases.dropdown_base import DynamicDropdownView
from frontend.interactions.bases.modal_base import ButtonDynamicModalView, DynamicModalView

from config import settings

from .major_handler import MajorHandler
from .profile_config import PROFILE_CONFIG
from .profile_handlers import EmailVerifier


class TryAgainView(discord.ui.View):
    def __init__(self, parent_cog, action):
        super().__init__(timeout=60)
        self.parent_cog = parent_cog
        self.action = action

    @discord.ui.button(label="Try Again", style=discord.ButtonStyle.primary)
    async def retry_button(self, interaction: discord.Interaction, _: discord.ui.Button):
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
            modal_view._modal.children[0].default = user.profile.name.first
            modal_view._modal.children[1].default = user.profile.name.last
            modal_view._modal.children[2].default = user.profile.student_id
            modal_view._modal.children[3].default = user.profile.school_email
            modal_view._modal.children[4].default = user.profile.graduation_year

        return await modal_view.initiate_from_interaction(interaction)

    async def get_majors(
        self, message: discord.Message, _user: User | None
    ) -> tuple[list[str], discord.Message]:
        """Get selected majors using dropdown base"""
        config = self.major_handler.get_dropdown_config(self.config["major_dropdown"])
        view = DynamicDropdownView(**config)

        values, message = await view.initiate_from_message(
            message, self.major_handler.get_help_text()
        )
        self.logger.debug(f"Dropdown values: {values}")

        if not values:
            return ["Not Set"], message

        # Combine selections from all dropdowns
        selected = []
        for dropdown_id in values:
            selected.extend(values[dropdown_id])

        max_majors = 2
        if len(selected) > max_majors:
            await message.edit(content=f"You can only select up to {max_majors} majors.", view=10)
            return ["Not Set"], message  # Limit to max 2 majors total

        return selected, message  # Limit to max 2 majors total

    async def verify_email(
        self, message: discord.Message, new_email: str, user: User | None
    ) -> bool:
        """Verify user's email using button modal base"""
        if user and new_email == user.profile.school_email:
            return True

        if not new_email.endswith("edu"):
            await message.edit(content="Invalid School email!")
            return False

        if not self.email_verifier.send_verification_email(message.author.id, new_email):
            await message.edit(content="Failed to send verification email.")
            return False

        verify_view = ButtonDynamicModalView(**self.config["verify_modal"])
        values, _ = await verify_view.initiate_from_message(message)

        if not values:
            return False
        return self.email_verifier.verify_code(message.author.id, values["verification_code"])

    async def handle_profile(self, interaction: discord.Interaction, action: str) -> None:
        """Handle profile creation and updates."""
        user = Database.get_document(User, interaction.user.id)
        self.logger.info(
            f"Profile {action} requested by {interaction.user} (ID: {interaction.user.id})"
        )

        if not await self._validate_action(interaction, action, user):
            return

        profile_data, message = await self.get_profile_data(interaction, action, user)
        if not profile_data or not message:
            self.logger.info(f"Profile {action} cancelled by {interaction.user}")
            return

        if not await self._validate_profile_data(profile_data, message, action):
            return

        selected_majors = await self._get_valid_majors(message, user)
        if not selected_majors:
            return

        if not await self.verify_email(message, profile_data["school_email"], user):
            return

        await self._save_profile(
            interaction,
            action,
            profile_data,
            {
                "selected_majors": selected_majors,
                "user": user,
                "message": message,
            },
        )

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

        if not (profile_data["first_name"].isalpha() and profile_data["last_name"].isalpha()):
            content += "Names cannot consist of numbers or special characters.\n"
            trycheck = True
        if not (profile_data["graduation_year"].isdigit()):
            content += "Graduation year must be a number.\n"
            trycheck = True
        if not (profile_data["student_id"].isdigit()):
            content += "Student ID must be a number.\n"
            trycheck = True

        grad_year_lower_bound = 1899
        grad_year_upper_bound = 2100
        if (profile_data["graduation_year"].isdigit()) and not (
            grad_year_lower_bound < int(profile_data["graduation_year"]) < grad_year_upper_bound
        ):
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
                if selected_majors != ["Not Set"]:
                    return selected_majors

                await message.edit(content="⚠️ Please select 1 or 2 majors.")
                time.sleep(1)

            except Exception as e:
                await message.edit(content=str(e))
                time.sleep(5)

    async def _save_profile(
        self,
        interaction: discord.Interaction,
        action: str,
        profile_data: dict,
        context: dict,
    ) -> None:
        """Save the user profile to the database."""
        selected_majors = context["selected_majors"]
        user = context["user"]
        message = context["message"]

        profile_data = {
            "name": UserName(first=profile_data["first_name"], last=profile_data["last_name"]),
            "major": selected_majors,
            "graduation_year": profile_data["graduation_year"],
            "school_email": profile_data["school_email"],
            "student_id": profile_data["student_id"],
        }

        if action == "create":
            new_user = User(_id=interaction.user.id, profile=UserProfile(**profile_data))
            Database.add_document(new_user)
            user = new_user
            self.logger.info(f"Created new profile for {interaction.user}")
        else:
            updates = {f"profile__{k}": v for k, v in profile_data.items()}
            Database.update_document(user, updates)
            user = Database.get_document(User, interaction.user.id)
            self.logger.info(f"Updated profile for {interaction.user}")

        # Show the profile using the final message
        await self.show_profile_embed(message, user)

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
            avatar_url = message_or_interaction.user.display_avatar.url
        else:
            avatar_url = message_or_interaction.author.display_avatar.url

        embed.set_thumbnail(url=avatar_url)
        embed.add_field(name="First Name", value=user.profile.name.first, inline=True)
        embed.add_field(name="Last Name", value=user.profile.name.last, inline=True)
        embed.add_field(name="Major", value=", ".join(user.profile.major), inline=True)
        embed.add_field(name="Graduation Year", value=user.profile.graduation_year, inline=True)
        embed.add_field(name="School Email", value=user.profile.school_email, inline=True)
        embed.add_field(name="Student ID", value=user.profile.student_id, inline=True)

        if is_interaction:
            if message_or_interaction.response.is_done():
                await message_or_interaction.edit_original_response(embed=embed)
            else:
                await message_or_interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await message_or_interaction.edit(content=None, embed=embed, view=None)

    async def show_profile(self, interaction: discord.Interaction) -> None:
        """Display the user's profile.

        Args:
            interaction: The Discord interaction
        """
        user = Database.get_document(User, interaction.user.id)
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
        user = Database.get_document(User, interaction.user.id)
        self.logger.info(f"Profile deletion requested by {interaction.user}")

        if not user:
            self.logger.warning(f"User {interaction.user} attempted to delete non-existent profile")
            await interaction.edit_original_response(content="You don't have a profile to delete.")
            return

        view = ConfirmDeleteView()
        await interaction.edit_original_response(
            content="⚠️ Are you sure you want to delete your profile? "
            "This action cannot be undone.",
            view=view,
        )

        await view.wait()
        if view.value:
            Database.delete_document(user)
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

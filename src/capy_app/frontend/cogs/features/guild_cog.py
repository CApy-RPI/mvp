"""Guild settings management cog."""

import logging
import discord
from typing import Optional
from discord import app_commands
from discord.ext import commands

from backend.db.database import Database as db
from frontend.interactions.bases.dropdown_base import DynamicDropdownView
from frontend.cogs.handlers.guild_handler_cog import GuildHandlerCog
from frontend import config_colors as colors
from frontend.interactions.checks.scopes import is_guild
from frontend.cogs.features.guild_config import ConfigConstructor
from config import settings
from frontend.interactions.bases.button_base import ConfirmDeleteView


@app_commands.guild_only()
class GuildCog(commands.Cog):
    """Server configuration management."""

    def __init__(self, bot: commands.Bot) -> None:
        super().__init__()
        self.bot = bot
        self.logger = logging.getLogger(
            f"discord.cog.{self.__class__.__name__.lower()}"
        )
        self.config = ConfigConstructor()

    async def _verify_guild_access(
        self, interaction: discord.Interaction, require_manage: bool = False
    ) -> tuple[bool, str]:
        """Verify guild access and permissions."""
        if not isinstance(interaction.guild, discord.Guild):
            return False, "This command can only be used in a server."

        if require_manage and not interaction.user.guild_permissions.manage_guild:
            return False, "You need 'Manage Server' permission to modify settings."

        guild_data = await GuildHandlerCog.ensure_guild_exists(interaction.guild.id)
        if not guild_data:
            return False, "Failed to access guild settings."

        return True, ""

    async def _process_settings_selection(
        self, interaction: discord.Interaction
    ) -> tuple[Optional[str], Optional[discord.Message]]:
        """Process settings type selection."""
        settings_view = DynamicDropdownView(**self.config.get_settings_type_dropdown())
        selections, message = await settings_view.initiate_from_interaction(
            interaction, "Select what you'd like to edit:"
        )

        if not selections or "settings_type" not in selections:
            return None, None

        return selections["settings_type"][0], message

    async def _process_configuration(
        self, setting_type: str, message: discord.Message, guild: discord.Guild
    ) -> Optional[dict]:
        """Process configuration selection."""
        dropdowns = (
            await self.config.create_channel_dropdown(guild)
            if setting_type == "channels"
            else await self.config.create_role_dropdown(guild)
        )

        config_view = DynamicDropdownView(
            dropdowns=dropdowns, **self.config.get_config_view_settings()
        )

        selections, message = await config_view.initiate_from_message(
            message, f"Select {setting_type} for each category:"
        )

        if not selections:
            await message.edit(content="Configuration cancelled.", view=None)
            return None

        return {
            f"{category}s__{name}": int(values[0]) if values else None
            for key, values in selections.items()
            for category, name in [key.split("_")]
        }

    @is_guild()
    @app_commands.command(name="server", description="Manage server settings")
    @app_commands.guilds(discord.Object(id=settings.DEBUG_GUILD_ID))
    @app_commands.describe(action="The action to perform with server settings")
    @app_commands.choices(
        action=[app_commands.Choice(name=n, value=n) for n in ["show", "edit", "clear"]]
    )
    async def server(self, interaction: discord.Interaction, action: str) -> None:
        """Handle server setting actions."""
        access_ok, error_msg = await self._verify_guild_access(
            interaction, require_manage=(action in ["edit", "clear"])
        )
        if not access_ok:
            await interaction.edit_original_response(content=error_msg)
            return

        try:
            guild_data = await GuildHandlerCog.ensure_guild_exists(interaction.guild.id)
            actions = {
                "show": self.show_settings,
                "edit": self.edit_settings,
                "clear": lambda i: self.clear_settings(i, guild_data),
            }
            await actions[action](interaction)

        except Exception as e:
            self.logger.error(f"Failed to handle server action {action}: {e}")
            await interaction.edit_original_response(
                content=f"An error occurred while performing {action}."
            )

    async def show_settings(self, interaction: discord.Interaction) -> None:
        """Display current server settings."""
        if not isinstance(interaction.guild, discord.Guild):
            raise TypeError("Interaction must be in a guild.")

        await interaction.response.defer(ephemeral=True)

        guild_data = await GuildHandlerCog.ensure_guild_exists(interaction.guild.id)
        if not guild_data:
            await interaction.edit_original_response(content="No settings configured.")
            return

        embed = discord.Embed(title="Server Settings", color=colors.GUILD)

        # Show channels
        channel_text = "\n".join(
            f"{prompt['label']}: {f'<#{getattr(guild_data.channels, name)}>' if getattr(guild_data.channels, name) else 'Not Set'}"
            for name, prompt in self.config.get_channel_prompts().items()
        )
        embed.add_field(
            name="Channels",
            value=channel_text or "No channels configured",
            inline=False,
        )

        # Show roles
        role_text = "\n".join(
            f"{prompt['label']}: {f'<@&{getattr(guild_data.roles, name)}>' if getattr(guild_data.roles, name) else 'Not Set'}"
            for name, prompt in self.config.get_role_prompts().items()
        )
        embed.add_field(
            name="Roles", value=role_text or "No roles configured", inline=False
        )

        await interaction.edit_original_response(embed=embed)

    async def edit_settings(self, interaction: discord.Interaction) -> None:
        """Edit server settings using the new dropdown framework."""
        if not isinstance(interaction.guild, discord.Guild):
            raise TypeError("Interaction must be in a guild.")

        try:
            setting_type, message = await self._process_settings_selection(interaction)
            if not setting_type or not message:
                return

            updates = await self._process_configuration(
                setting_type, message, interaction.guild
            )
            if not updates:
                return

            guild_data = await GuildHandlerCog.ensure_guild_exists(interaction.guild.id)
            if not guild_data:
                await message.edit(content="Failed to access guild data.", view=None)
                return

            db.update_document(guild_data, updates)
            await self.show_settings(interaction)

        except Exception as e:
            self.logger.error(f"Error during settings edit: {e}")
            error_msg = "An error occurred during settings configuration."
            if message:
                await message.edit(content=error_msg, view=None)
            else:
                await interaction.followup.send(error_msg, view=None)

    async def clear_settings(
        self, interaction: discord.Interaction, guild_data
    ) -> None:
        """Clear all server settings."""
        view = ConfirmDeleteView()
        value, message = await view.initiate_from_interaction(
            interaction,
            self.config.get_clear_settings_prompt(),
        )

        if value:
            # Clear all settings
            updates = {
                "channels": {},
                "roles": {},
            }
            db.update_document(guild_data, updates)


async def setup(bot: commands.Bot) -> None:
    """Set up the Guild cog."""
    await bot.add_cog(GuildCog(bot))

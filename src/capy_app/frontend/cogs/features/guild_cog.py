"""Guild settings management cog."""

import logging
import typing
import discord
from discord import app_commands
from discord.ext import commands

from backend.db.database import Database as db
from .guild_views import (
    ChannelSelectView,
    RoleSelectView,
    SettingsSelectView,
    ClearSettingsView,
)
from .guild_handlers import (
    handle_channel_update,
    handle_role_update,
)
from frontend.cogs.handlers.guild_handler_cog import GuildHandlerCog
from frontend import config_colors as colors
from frontend.interactions.checks.scopes import is_guild
from config import settings


@app_commands.guild_only()
class GuildCog(commands.Cog):
    """Server configuration management."""

    def __init__(self, bot: commands.Bot) -> None:
        super().__init__()
        self.bot = bot
        self.logger = logging.getLogger("discord.guild")

        # Define configuration categories
        self.channels = {
            "reports": "Channel for report submissions",
            "announcements": "Channel for announcements",
            "moderator": "Channel for moderator communications",
        }

        self.roles = {
            "visitor": "Role for visitors",
            "member": "Role for verified members",
            "eboard": "Role for executive board members",
            "admin": "Role for administrators",
        }

    async def _handle_settings_select(
        self, interaction: discord.Interaction, selection: str, guild_data: typing.Any
    ) -> None:
        """Handle settings selection and updates."""
        if not isinstance(interaction.guild, discord.Guild):
            err = TypeError("Interaction must be in a guild.")
            self.logger.error(err)
            raise err

        self.logger.info(
            f"Settings update initiated for {interaction.guild} (ID: {interaction.guild.id}), selection: {selection}"
        )

        if selection in ["channels", "all"]:
            channel_view = ChannelSelectView(self.channels)
            await interaction.edit_original_response(
                content="Select channels for each category:", view=channel_view
            )
            await channel_view.wait()

            if channel_view.value is False:
                self.logger.info(
                    f"Channel settings update cancelled for {interaction.guild}"
                )
                await interaction.edit_original_response(
                    content="Cancelled channel settings update.", embed=None, view=None
                )
                return

            if not channel_view.value or not await handle_channel_update(
                interaction, channel_view, guild_data, self.channels
            ):
                self.logger.error(
                    f"Failed to update channel settings for {interaction.guild}"
                )
                await interaction.edit_original_response(
                    content="Failed to update channel settings.", embed=None, view=None
                )
                return

            self.logger.info(
                f"Successfully updated channel settings for {interaction.guild}"
            )

        if selection in ["roles", "all"]:
            role_view = RoleSelectView(self.roles)
            await interaction.edit_original_response(
                content="Select roles for each category:", view=role_view
            )
            await role_view.wait()

            if role_view.value is False:
                self.logger.info(
                    f"Role settings update cancelled for {interaction.guild}"
                )
                await interaction.edit_original_response(
                    content="Cancelled role settings update.", embed=None, view=None
                )
                return

            if not role_view.value or not await handle_role_update(
                interaction, role_view, guild_data, self.roles
            ):
                self.logger.error(
                    f"Failed to update role settings for {interaction.guild}"
                )
                await interaction.edit_original_response(
                    content="Failed to update role settings.", embed=None, view=None
                )
                return

            self.logger.info(
                f"Successfully updated role settings for {interaction.guild}"
            )

        await self.show_settings(interaction)

    @is_guild()
    @app_commands.guilds(discord.Object(id=settings.DEBUG_GUILD_ID))
    @app_commands.command(name="server", description="Manage server settings")
    @app_commands.describe(action="The action to perform with server settings")
    @app_commands.choices(
        action=[app_commands.Choice(name=n, value=n) for n in ["show", "edit", "clear"]]
    )
    async def server(self, interaction: discord.Interaction, action: str) -> None:
        """Handle server setting actions."""
        await interaction.response.defer(ephemeral=True)
        self.logger.info(
            f"Server settings {action} requested by {interaction.user} in {interaction.guild}"
        )

        if not isinstance(interaction.user, discord.Member):
            self.logger.warning(
                f"Non-member {interaction.user} attempted to use server command"
            )
            await interaction.edit_original_response(
                content="This command can only be used in a server."
            )
            return

        if (
            action in ["edit", "clear"]
            and not interaction.user.guild_permissions.manage_guild
        ):
            await interaction.edit_original_response(
                content="You need 'Manage Server' permission to modify settings."
            )
            return

        try:
            if not isinstance(interaction.guild, discord.Guild):
                await interaction.edit_original_response(
                    content="This command can only be used in a server."
                )
                return

            guild_data = await GuildHandlerCog.ensure_guild_exists(interaction.guild.id)
            if not guild_data:
                await interaction.edit_original_response(
                    content="Failed to access guild settings."
                )
                return

            actions = {
                "show": self.show_settings,
                "edit": self.edit_settings,
                "clear": self.clear_settings,
            }
            await actions[action](interaction)

        except Exception as e:
            self.logger.error(f"Failed to handle server action {action}: {e}")
            await interaction.edit_original_response(
                content=f"An error occurred while performing {action}."
            )

    async def show_settings(self, interaction: discord.Interaction) -> None:
        """Display current server settings.

        Args:
            interaction: The Discord interaction
        """
        if not isinstance(interaction.guild, discord.Guild):
            err = TypeError("Interaction must be in a guild.")
            self.logger.error(err)
            raise err

        guild_data = await GuildHandlerCog.ensure_guild_exists(interaction.guild.id)
        if not guild_data:
            await interaction.edit_original_response(
                content="No settings configured.", embed=None, view=None
            )
            return

        embed = discord.Embed(title="Server Settings", color=colors.GUILD)

        # Show channels
        channel_text = "\n".join(
            f"{name.title()}: {f'<#{getattr(guild_data.channels, name)}>' if getattr(guild_data.channels, name) else 'Not Set'}"
            for name in self.channels
        )
        embed.add_field(
            name="Channels",
            value=channel_text or "No channels configured",
            inline=False,
        )

        # Show roles
        role_text = "\n".join(
            f"{name.title()}: {f'<@&{getattr(guild_data.roles, name)}>' if getattr(guild_data.roles, name) else 'Not Set'}"
            for name in self.roles
        )
        embed.add_field(
            name="Roles", value=role_text or "No roles configured", inline=False
        )

        await interaction.edit_original_response(content=None, embed=embed, view=None)

    async def edit_settings(self, interaction: discord.Interaction) -> None:
        """Edit server settings using views."""
        if not isinstance(interaction.guild, discord.Guild):
            err = TypeError("Interaction must be in a guild.")
            self.logger.error(err)
            raise err

        settings_view = SettingsSelectView()
        await interaction.edit_original_response(
            content="Select what you'd like to edit:", view=settings_view
        )
        await settings_view.wait()

        if not settings_view.selected_setting:
            await interaction.edit_original_response(
                content="Settings editing cancelled.", embed=None, view=None
            )
            return

        try:
            guild_data = await GuildHandlerCog.ensure_guild_exists(interaction.guild.id)
            if not guild_data:
                await interaction.edit_original_response(
                    content="Failed to access guild settings.", embed=None, view=None
                )
                return

            await self._handle_settings_select(
                interaction, settings_view.selected_setting, guild_data
            )

        except Exception as e:
            self.logger.error(f"Failed to handle settings edit: {e}")
            await interaction.edit_original_response(
                content="An error occurred while editing settings.",
                embed=None,
                view=None,
            )

    async def clear_settings(self, interaction: discord.Interaction) -> None:
        """Clear server settings."""
        if not isinstance(interaction.guild, discord.Guild):
            err = TypeError("Interaction must be in a guild.")
            self.logger.error(err)
            raise err

        clear_view = ClearSettingsView()
        await interaction.edit_original_response(
            content="Select what you'd like to clear:", view=clear_view
        )
        await clear_view.wait()

        if not clear_view.selected_setting:
            self.logger.info(f"Settings clearing cancelled for {interaction.guild}")
            await interaction.edit_original_response(
                content="Settings clearing cancelled.", embed=None, view=None
            )
            return

        try:
            guild_data = await GuildHandlerCog.ensure_guild_exists(interaction.guild.id)
            if not guild_data:
                self.logger.error(
                    f"Failed to access guild settings for {interaction.guild}"
                )
                await interaction.edit_original_response(
                    content="Failed to access guild settings.", embed=None, view=None
                )
                return

            updates: dict[str, None] = {}
            if clear_view.selected_setting in ["channels", "all"]:
                updates.update(
                    {f"channels__{channel}": None for channel in self.channels}
                )
            if clear_view.selected_setting in ["roles", "all"]:
                updates.update({f"roles__{role}": None for role in self.roles})

            db.update_document(guild_data, updates)
            self.logger.info(
                f"Successfully cleared {clear_view.selected_setting} settings for {interaction.guild}"
            )
            await interaction.edit_original_response(
                content=f"Successfully cleared {clear_view.selected_setting} settings!",
                embed=None,
                view=None,
            )

        except Exception as e:
            self.logger.error(f"Failed to clear settings for {interaction.guild}: {e}")
            await interaction.edit_original_response(
                content="Failed to clear settings.", embed=None, view=None
            )


async def setup(bot: commands.Bot) -> None:
    """Set up the Guild cog.

    Args:
        bot: The Discord bot instance
    """
    await bot.add_cog(GuildCog(bot))

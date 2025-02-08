"""Guild settings management cog."""

import logging
import discord
from discord import app_commands
from discord.ext import commands

from backend.db.database import Database as db
from frontend.utils import embed_colors as colors
from frontend.cogs.handlers.guild_handler_cog import GuildHandlerCog
from frontend.utils.interactions.guild.views import (
    ChannelSelectView,
    RoleSelectView,
    SettingsSelectView,
)
from frontend.utils.interactions.guild.handlers import (
    handle_channel_update,
    handle_role_update,
)
from config import settings


@app_commands.guild_only()
class GuildCog(commands.Cog):
    """Server configuration management."""

    def __init__(self, bot: commands.Bot) -> None:
        super().__init__()
        self.bot = bot
        self.logger = logging.getLogger("discord.guild")

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

    @app_commands.guilds(discord.Object(id=settings.DEBUG_GUILD_ID))
    @app_commands.guild_only()
    @app_commands.command(name="server", description="Manage server settings")
    @app_commands.describe(action="The action to perform with server settings")
    @app_commands.choices(
        action=[
            app_commands.Choice(name="show", value="show"),
            app_commands.Choice(name="edit", value="edit"),
            app_commands.Choice(name="clear", value="clear"),
        ]
    )
    async def server(self, interaction: discord.Interaction, action: str):
        await interaction.response.defer(ephemeral=True)
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.edit_original_response(
                content="You don't have permission to edit server settings.",
                embed=None,
                view=None,
            )
            return

        if action == "show":
            await self.show_settings(interaction)
        elif action == "edit":
            await self.edit_settings(interaction)
        elif action == "clear":
            await self.clear_settings(interaction)

    async def show_settings(self, interaction: discord.Interaction) -> None:
        """Display current server settings.

        Args:
            interaction: The Discord interaction
        """
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
        view = SettingsSelectView(self)
        select = discord.ui.Select(
            placeholder="Choose what to edit",
            options=[
                discord.SelectOption(
                    label="Channels",
                    value="channels",
                    description="Edit channel settings",
                ),
                discord.SelectOption(
                    label="Roles", value="roles", description="Edit role settings"
                ),
                discord.SelectOption(
                    label="All", value="all", description="Edit all settings"
                ),
            ],
        )

        async def select_callback(interaction: discord.Interaction) -> None:
            try:
                await interaction.response.defer()
                guild_data = await GuildHandlerCog.ensure_guild_exists(
                    interaction.guild.id
                )
                if not guild_data:
                    await interaction.edit_original_response(
                        content="Failed to access guild settings.",
                        embed=None,
                        view=None,
                    )
                    return

                if select.values[0] == "channels":
                    channel_view = ChannelSelectView(self.channels)
                    await interaction.edit_original_response(
                        content="Select channels for each category:",
                        embed=None,
                        view=channel_view,
                    )
                    view.current_view = channel_view
                    await view.current_view.wait()

                    if not view.current_view.value:  # Cancelled or timeout
                        try:
                            await interaction.edit_original_response(
                                content="Channel editing cancelled.",
                                embed=None,
                                view=None,
                            )
                        except discord.NotFound:
                            pass  # Message already handled
                        return

                    try:
                        if await handle_channel_update(
                            interaction, view.current_view, guild_data, self.channels
                        ):
                            await self.show_settings(interaction)
                    except discord.NotFound:
                        pass  # Message already handled

                elif select.values[0] == "roles":
                    role_view = RoleSelectView(self.roles)
                    await interaction.edit_original_response(
                        content="Select roles for each category:",
                        embed=None,
                        view=role_view,
                    )
                    view.current_view = role_view
                    await view.current_view.wait()

                    if not view.current_view.value:  # Cancelled or timeout
                        try:
                            await interaction.edit_original_response(
                                content="Role editing cancelled.", embed=None, view=None
                            )
                        except discord.NotFound:
                            pass  # Message already handled
                        return

                    try:
                        if await handle_role_update(
                            interaction, view.current_view, guild_data, self.roles
                        ):
                            await self.show_settings(interaction)
                    except discord.NotFound:
                        pass  # Message already handled

                elif select.values[0] == "all":
                    # Handle channels first
                    channel_view = ChannelSelectView(self.channels)
                    await interaction.edit_original_response(
                        content="First, select channels for each category:",
                        view=channel_view,
                    )
                    await channel_view.wait()

                    if not channel_view.value:  # Cancelled or timeout
                        try:
                            await interaction.edit_original_response(
                                content="Settings editing cancelled.",
                                embed=None,
                                view=None,
                            )
                        except discord.NotFound:
                            pass  # Message already handled
                        return

                    try:
                        if await handle_channel_update(
                            interaction, channel_view, guild_data, self.channels
                        ):
                            # Then handle roles
                            role_view = RoleSelectView(self.roles)
                            await interaction.edit_original_response(
                                content="Now, select roles for each category:",
                                view=role_view,
                            )
                            await role_view.wait()

                            if not role_view.value:  # Cancelled or timeout
                                try:
                                    await interaction.edit_original_response(
                                        content="Settings editing cancelled.",
                                        embed=None,
                                        view=None,
                                    )
                                except discord.NotFound:
                                    pass  # Message already handled
                                return

                            try:
                                if await handle_role_update(
                                    interaction, role_view, guild_data, self.roles
                                ):
                                    await self.show_settings(interaction)
                            except discord.NotFound:
                                pass  # Message already handled
                    except discord.NotFound:
                        pass  # Message already handled

            except Exception as e:
                self.logger.error(f"Failed to handle settings edit: {e}")
                try:
                    await interaction.edit_original_response(
                        content="An error occurred while editing settings.",
                        embed=None,
                        view=None,
                    )
                except discord.NotFound:
                    pass  # Message already handled

        select.callback = select_callback
        view.add_item(select)
        await interaction.edit_original_response(
            content="Select what you'd like to edit:", view=view
        )

    async def clear_settings(self, interaction: discord.Interaction) -> None:
        """Clear server settings.

        Args:
            interaction: The Discord interaction
        """
        options = [
            discord.SelectOption(
                label="Channels",
                value="channels",
                description="Clear all channel settings",
            ),
            discord.SelectOption(
                label="Roles",
                value="roles",
                description="Clear all role settings",
            ),
            discord.SelectOption(
                label="All",
                value="all",
                description="Clear all server settings",
            ),
        ]

        select = discord.ui.Select(
            placeholder="Choose what to clear",
            options=options,
        )
        view = discord.ui.View().add_item(select)

        async def select_callback(interaction: discord.Interaction) -> None:
            await interaction.response.defer()

            guild_data = await GuildHandlerCog.ensure_guild_exists(interaction.guild.id)
            if not guild_data:
                await interaction.edit_original_response(
                    content="Failed to access guild settings.", embed=None, view=None
                )
                return

            updates: dict[str, None] = {}
            if select.values[0] in ["channels", "all"]:
                updates.update(
                    {f"channels__{channel}": None for channel in self.channels}
                )
            if select.values[0] in ["roles", "all"]:
                updates.update({f"roles__{role}": None for role in self.roles})

            try:
                db.update_document(guild_data, updates)
                await interaction.edit_original_response(
                    content=f"Successfully cleared {select.values[0]} settings!",
                    embed=None,
                    view=None,
                )
            except Exception as e:
                self.logger.error(f"Failed to clear settings: {e}")
                await interaction.edit_original_response(
                    content="Failed to clear settings.", embed=None, view=None
                )

        select.callback = select_callback
        await interaction.edit_original_response(
            content="Select what you'd like to clear:", view=view
        )


async def setup(bot: commands.Bot) -> None:
    """Set up the Guild cog."""
    await bot.add_cog(GuildCog(bot))

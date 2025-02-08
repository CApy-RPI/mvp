"""Guild settings management cog."""

import typing
import logging
import discord
from discord import app_commands
from discord.ext import commands

from backend.db.database import Database as db
from frontend.utils import embed_colors as colors
from frontend.cogs.handlers.guild_handler_cog import GuildHandlerCog
from config import settings
from frontend.utils.view_bases import BaseDropdownView


class ChannelSelectView(BaseDropdownView):
    def __init__(self, channels: dict[str, str]):
        super().__init__()
        self.selected_channels = {}

        for channel_name, description in channels.items():
            select = discord.ui.ChannelSelect(
                placeholder=f"Select {channel_name.title()} channel",
                channel_types=[discord.ChannelType.text],
                custom_id=f"channel_{channel_name}",
            )
            select.callback = self.create_callback(channel_name)
            self.add_item(select)

    def create_callback(self, channel_name: str):
        async def callback(interaction: discord.Interaction):
            try:
                values = interaction.data.get("values", [])
                if values:
                    self.selected_channels[channel_name] = int(values[0])
                else:  # Handle skip
                    self.selected_channels.pop(channel_name, None)
                await interaction.response.defer()
            except Exception as e:
                await interaction.response.send_message(
                    "Failed to process channel selection.", ephemeral=True
                )

        return callback


class RoleSelectView(BaseDropdownView):
    def __init__(self, roles: dict[str, str]):
        super().__init__()
        self.selected_roles = {}

        for role_name, description in roles.items():
            select = discord.ui.RoleSelect(
                placeholder=f"Select {role_name.title()} role",
                custom_id=f"role_{role_name}",
            )
            select.callback = self.create_callback(role_name)
            self.add_item(select)

    def create_callback(self, role_name: str):
        async def callback(interaction: discord.Interaction):
            try:
                values = interaction.data.get("values", [])
                if values:
                    self.selected_roles[role_name] = values[0]
                else:  # Handle skip
                    self.selected_roles.pop(role_name, None)
                await interaction.response.defer()
            except Exception as e:
                await interaction.response.send_message(
                    "Failed to process role selection.", ephemeral=True
                )

        return callback


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
        if action == "show":
            await self.show_settings(interaction)
        elif action == "edit":
            await self.edit_settings(interaction)
        elif action == "clear":
            await self.clear_settings(interaction)

    async def show_settings(self, interaction: discord.Interaction):
        """Display current server settings."""
        await interaction.response.defer(ephemeral=True)

        guild_data = await GuildHandlerCog.ensure_guild_exists(interaction.guild.id)
        if not guild_data:
            await interaction.followup.send("No settings configured.", ephemeral=True)
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

        await interaction.followup.send(embed=embed, ephemeral=True)

    async def edit_settings(self, interaction: discord.Interaction):
        """Edit server settings using views."""

        class SettingsSelectView(discord.ui.View):
            def __init__(self, parent_cog):
                super().__init__(timeout=180.0)
                self.parent_cog = parent_cog

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

        async def select_callback(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            if select.values[0] == "channels":
                await self.edit_channels(interaction)
            elif select.values[0] == "roles":
                await self.edit_roles(interaction)
            elif select.values[0] == "all":
                await self.edit_all(interaction)

        select.callback = select_callback
        view.add_item(select)
        await interaction.response.send_message(
            "Select what you'd like to edit:", view=view, ephemeral=True
        )

    async def edit_all(self, interaction: discord.Interaction) -> None:
        """Edit all settings simultaneously."""
        # First handle channels
        await self.edit_channels(interaction)
        # Then handle roles
        await self.edit_roles(interaction)

    async def edit_channels(self, interaction: discord.Interaction) -> None:
        """Edit channel settings."""
        view = ChannelSelectView(self.channels)
        await interaction.followup.send(
            "Select channels for each category:",
            view=view,
            ephemeral=True,
        )

        await view.wait()
        if not view.value:  # Cancelled
            await interaction.followup.send(
                "Cancelled channel editing.", ephemeral=True
            )
            return

        if not view.selected_channels:
            await interaction.followup.send(
                "No channels were selected.", ephemeral=True
            )
            return

        guild_data = await GuildHandlerCog.ensure_guild_exists(interaction.guild.id)
        if not guild_data:
            await interaction.followup.send(
                "Failed to access guild settings.", ephemeral=True
            )
            return

        updates: dict[str, typing.Any] = {
            f"channels__{name}": channel_id
            for name, channel_id in view.selected_channels.items()
        }

        try:
            db.update_document(guild_data, updates)
            await interaction.followup.send(
                "Channel settings updated successfully!", ephemeral=True
            )
            # Show updated settings
            await self.show_settings(interaction)
        except Exception as e:
            self.logger.error(f"Failed to update channels: {e}")
            await interaction.followup.send(
                "Failed to update channel settings.", ephemeral=True
            )

    async def edit_roles(self, interaction: discord.Interaction) -> None:
        """Edit role settings."""
        view = RoleSelectView(self.roles)
        await interaction.followup.send(
            "Select roles for each category:",
            view=view,
            ephemeral=True,
        )

        await view.wait()
        if not view.value:  # Cancelled
            await interaction.followup.send("Cancelled role editing.", ephemeral=True)
            return

        if not view.selected_roles:
            await interaction.followup.send("No roles were selected.", ephemeral=True)
            return

        guild_data = await GuildHandlerCog.ensure_guild_exists(interaction.guild.id)
        if not guild_data:
            await interaction.followup.send(
                "Failed to access guild settings.", ephemeral=True
            )
            return

        updates: dict[str, typing.Any] = {
            f"roles__{name}": role_id for name, role_id in view.selected_roles.items()
        }

        try:
            db.update_document(guild_data, updates)
            await interaction.followup.send(
                "Role settings updated successfully!", ephemeral=True
            )
            # Show updated settings
            await self.show_settings(interaction)
        except Exception as e:
            self.logger.error(f"Failed to update roles: {e}")
            await interaction.followup.send(
                "Failed to update role settings.", ephemeral=True
            )

    async def clear_settings(self, interaction: discord.Interaction):
        """Clear server settings."""
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

        async def select_callback(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            guild_data = await GuildHandlerCog.ensure_guild_exists(interaction.guild.id)

            if not guild_data:
                await interaction.followup.send(
                    "Failed to access guild settings.", ephemeral=True
                )
                return

            updates = {}
            if select.values[0] in ["channels", "all"]:
                for channel in self.channels:
                    updates[f"channels__{channel}"] = None

            if select.values[0] in ["roles", "all"]:
                for role in self.roles:
                    updates[f"roles__{role}"] = None

            try:
                db.update_document(guild_data, updates)
                await interaction.followup.send(
                    f"Successfully cleared {select.values[0]} settings!", ephemeral=True
                )
            except Exception as e:
                self.logger.error(f"Failed to clear settings: {e}")
                await interaction.followup.send(
                    "Failed to clear settings.", ephemeral=True
                )

        select.callback = select_callback
        await interaction.response.send_message(
            "Select what you'd like to clear:", view=view, ephemeral=True
        )


async def setup(bot: commands.Bot) -> None:
    """Set up the Guild cog."""
    await bot.add_cog(GuildCog(bot))

"""Guild settings management cog."""

import typing
import logging
import discord
from discord import app_commands
from discord.ext import commands

from backend.db.database import Database as db
from backend.db.documents.guild import Guild
from frontend.utils import colors
from frontend.cogs.handlers.guild_handler_cog import GuildHandlerCog


class ChannelSelectView(discord.ui.View):
    def __init__(self, channels: dict[str, str]):
        super().__init__()
        self.selected_channels = {}

        for channel_name, description in channels.items():
            select = discord.ui.ChannelSelect(
                placeholder=f"Select {channel_name.title()} channel",
                channel_types=[discord.ChannelType.text],
                custom_id=f"channel_{channel_name}",
            )

            def make_callback(name):
                async def callback(interaction: discord.Interaction):
                    self.selected_channels[name] = select.values[0].id
                    await interaction.response.defer()
                    if len(self.selected_channels) == len(channels):
                        self.stop()

                return callback

            select.callback = make_callback(channel_name)
            self.add_item(select)

    async def wait_for_selections(self, timeout=180.0):
        try:
            await self.wait()
            return self.selected_channels
        except TimeoutError:
            return None


class RoleSelectView(discord.ui.View):
    def __init__(self, roles: dict[str, str]):
        super().__init__()
        self.selected_roles = {}

        for role_name, description in roles.items():
            select = discord.ui.RoleSelect(
                placeholder=f"Select {role_name.title()} role",
                custom_id=f"role_{role_name}",
            )

            def make_callback(name):
                async def callback(interaction: discord.Interaction):
                    self.selected_roles[name] = str(select.values[0].id)
                    await interaction.response.defer()
                    if len(self.selected_roles) == len(roles):
                        self.stop()

                return callback

            select.callback = make_callback(role_name)
            self.add_item(select)

    async def wait_for_selections(self, timeout=180.0):
        try:
            await self.wait()
            return self.selected_roles
        except TimeoutError:
            return None


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

    @app_commands.command(name="server", description="Manage server settings")
    @app_commands.describe(action="The action to perform with server settings")
    @app_commands.choices(
        action=[
            app_commands.Choice(name="show", value="show"),
            app_commands.Choice(name="edit", value="edit"),
        ]
    )
    async def server(self, interaction: discord.Interaction, action: str):
        if action == "show":
            await self.show_settings(interaction)
        elif action == "edit":
            await self.edit_settings(interaction)

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
        options = [
            discord.SelectOption(
                label="Channels", value="channels", description="Edit channel settings"
            ),
            discord.SelectOption(
                label="Roles", value="roles", description="Edit role settings"
            ),
        ]

        select = discord.ui.Select(placeholder="Choose what to edit", options=options)
        view = discord.ui.View().add_item(select)

        async def select_callback(interaction: discord.Interaction):
            if select.values[0] == "channels":
                await self.edit_channels(interaction)
            else:
                await self.edit_roles(interaction)

        select.callback = select_callback
        await interaction.response.send_message(
            "Select what you'd like to edit:", view=view, ephemeral=True
        )

    async def edit_channels(self, interaction: discord.Interaction) -> None:
        """Edit channel settings."""
        view = ChannelSelectView(self.channels)
        await interaction.followup.send(
            "Select channels for each category:", view=view, ephemeral=True
        )

        selected_channels = await view.wait_for_selections()
        if not selected_channels:
            await interaction.followup.send(
                "Channel selection timed out.", ephemeral=True
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
            for name, channel_id in selected_channels.items()
        }

        try:
            db.update_document(Guild, guild_data.id, updates)
            await interaction.followup.send(
                "Channel settings updated successfully!", ephemeral=True
            )
        except Exception as e:
            self.logger.error(f"Failed to update channels: {e}")
            await interaction.followup.send(
                "Failed to update channel settings.", ephemeral=True
            )

    async def edit_roles(self, interaction: discord.Interaction) -> None:
        """Edit role settings."""
        view = RoleSelectView(self.roles)
        await interaction.followup.send(
            "Select roles for each category:", view=view, ephemeral=True
        )

        selected_roles = await view.wait_for_selections()
        if not selected_roles:
            await interaction.followup.send("Role selection timed out.", ephemeral=True)
            return

        guild_data = await GuildHandlerCog.ensure_guild_exists(interaction.guild.id)
        if not guild_data:
            await interaction.followup.send(
                "Failed to access guild settings.", ephemeral=True
            )
            return

        updates: dict[str, typing.Any] = {
            f"roles__{name}": role_id for name, role_id in selected_roles.items()
        }

        try:
            db.update_document(Guild, guild_data.id, updates)
            await interaction.followup.send(
                "Role settings updated successfully!", ephemeral=True
            )
        except Exception as e:
            self.logger.error(f"Failed to update roles: {e}")
            await interaction.followup.send(
                "Failed to update role settings.", ephemeral=True
            )


async def setup(bot: commands.Bot) -> None:
    """Set up the Guild cog."""
    await bot.add_cog(GuildCog(bot))

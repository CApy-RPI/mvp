"""Guild settings management cog."""

import typing
import logging
import discord
from discord import app_commands
from discord.ext import commands

from config import settings
from backend.db.database import Database as db
from frontend.utils import colors
from frontend.cogs.handler.guild_handler_cog import GuildHandlerCog


@app_commands.guild_only()
class GuildCog(commands.Cog):
    """Server configuration management."""

    def __init__(self, bot: commands.Bot) -> None:
        """Initialize guild management cog."""
        super().__init__()
        self.bot = bot
        self.logger = logging.getLogger("discord.guild")

    channels = {
        "reports": "Channel for report submissions",
        "announcements": "Channel for announcements",
        "moderator": "Channel for moderator communications",
    }

    roles = {
        "visitor": "Role for visitors",
        "member": "Role for verified members",
        "eboard": "Role for executive board members",
        "admin": "Role for administrators",
    }

    @app_commands.command(name="show")
    async def show_settings(self, interaction: discord.Interaction) -> None:
        """Display current server settings."""
        guild_data = await GuildHandlerCog.ensure_guild_exists(interaction.guild.id)
        if not guild_data:
            await interaction.response.send_message(
                "No settings configured.", ephemeral=True
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

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="channel")
    @app_commands.describe(
        name="Which channel setting to modify", channel="The channel to set"
    )
    @app_commands.choices(
        name=[
            app_commands.Choice(name="Reports", value="reports"),
            app_commands.Choice(name="Announcements", value="announcements"),
            app_commands.Choice(name="Moderator", value="moderator"),
        ]
    )
    async def edit_channel(
        self, interaction: discord.Interaction, name: str, channel: discord.TextChannel
    ) -> None:
        """Edit a channel setting."""
        await interaction.response.defer(ephemeral=True)

        try:
            guild_data = await GuildHandlerCog.ensure_guild_exists(interaction.guild.id)
            if not guild_data:
                await interaction.followup.send(
                    "Could not access settings.", ephemeral=True
                )
                return

            setattr(guild_data.channels, name, channel.id)
            guild_data.save()

            await interaction.followup.send(
                f"Updated {name} channel to {channel.mention}", ephemeral=True
            )

        except Exception as e:
            self.logger.error(f"Failed to update channel: {e}")
            await interaction.followup.send("Failed to update setting.", ephemeral=True)

    @app_commands.command(name="role")
    @app_commands.describe(name="Which role setting to modify", role="The role to set")
    @app_commands.choices(
        name=[
            app_commands.Choice(name="Visitor", value="visitor"),
            app_commands.Choice(name="Member", value="member"),
            app_commands.Choice(name="E-Board", value="eboard"),
            app_commands.Choice(name="Admin", value="admin"),
        ]
    )
    async def edit_role(
        self, interaction: discord.Interaction, name: str, role: discord.Role
    ) -> None:
        """Edit a role setting."""
        await interaction.response.defer(ephemeral=True)

        try:
            guild_data = await GuildHandlerCog.ensure_guild_exists(interaction.guild.id)
            if not guild_data:
                await interaction.followup.send(
                    "Could not access settings.", ephemeral=True
                )
                return

            setattr(guild_data.roles, name, str(role.id))
            guild_data.save()

            await interaction.followup.send(
                f"Updated {name} role to {role.mention}", ephemeral=True
            )

        except Exception as e:
            self.logger.error(f"Failed to update role: {e}")
            await interaction.followup.send("Failed to update setting.", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    """Set up the Guild cog."""
    await bot.add_cog(GuildCog(bot))

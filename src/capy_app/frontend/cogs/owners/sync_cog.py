"""Command synchronization cog.

This module handles synchronizing application commands with Discord:
- Manual sync via command
- Slash command sync
- Debug guild sync

#TODO: Add sync status tracking
"""

import logging
from typing import List, Optional
import discord
from discord.ext import commands
from discord import app_commands
from frontend.utils.embed_statuses import success_embed, error_embed
from config import settings
from frontend.interactions.checks.owners import is_owner


class SyncCog(commands.Cog):
    """Cog for synchronizing application commands."""

    def __init__(self, bot: commands.Bot) -> None:
        """Initialize the sync cog.

        Args:
            bot: The Discord bot instance
        """
        self.bot = bot
        self.logger = logging.getLogger(
            f"discord.cog.{self.__class__.__name__.lower()}"
        )

    async def _sync_commands(
        self, debug_guild: Optional[discord.Guild]
    ) -> List[discord.app_commands.AppCommand]:
        """Synchronize commands with Discord.

        Args:
            debug_guild: Optional guild to sync commands to

        Returns:
            List of synced commands

        #! Note: This operation can be rate limited
        """
        self.logger.info("Syncing application commands...")
        if debug_guild:
            self.logger.info(f"Connected to debug guild: {debug_guild.name}")
        return await self.bot.tree.sync(guild=debug_guild)

    @commands.command(name="sync", hidden=True)
    @commands.is_owner()
    async def sync(self, ctx: commands.Context[commands.Bot]) -> None:
        """Sync commands manually (owner only)."""
        try:
            debug_guild = self.bot.get_guild(settings.DEBUG_GUILD_ID)
            synced = await self._sync_commands(debug_guild)

            description = (
                f"✅ Successfully synced {len(synced)} application commands!\n"
                f"Commands:\n{"\n".join([cmd.name for cmd in synced])}"
            )
            await ctx.send(embed=success_embed("Sync Commands", description))

        except Exception as e:
            self.logger.error(f"Failed to sync commands: {e}")
            await ctx.send(
                embed=error_embed("Sync Commands", f"❌ Failed to sync commands: {e}")
            )

    @is_owner()
    @app_commands.guilds(discord.Object(id=settings.DEBUG_GUILD_ID))
    @app_commands.command(name="sync", description="Sync application commands")
    async def sync_slash(self, interaction: discord.Interaction) -> None:
        """Sync commands via slash command."""
        try:
            debug_guild = self.bot.get_guild(settings.DEBUG_GUILD_ID)
            synced = await self._sync_commands(debug_guild)

            description = (
                f"✅ Successfully synced {len(synced)} application commands!\n"
                f"Commands:\n{"\n".join([cmd.name for cmd in synced])}"
            )
            await interaction.response.send_message(
                embed=success_embed("Sync Commands", description)
            )

        except Exception as e:
            self.logger.error(f"Failed to sync commands: {e}")
            await interaction.response.send_message(
                embed=error_embed("Sync Commands", f"❌ Failed to sync commands: {e}")
            )


async def setup(bot: commands.Bot) -> None:
    """Set up the Sync cog."""
    await bot.add_cog(SyncCog(bot))

"""Guild handler cog for managing guild database entries."""

import logging
import discord
from discord.ext import commands

from backend.db.database import Database as db
from backend.db.documents.guild import Guild


class GuildHandlerCog(commands.Cog):
    """A cog for handling guild joins and database management."""

    def __init__(self, bot: commands.Bot) -> None:
        """Initialize the GuildHandler cog.

        Args:
            bot: The Discord bot instance
        """
        self.bot = bot
        self.logger = logging.getLogger(
            f"discord.cog.{self.__class__.__name__.lower()}"
        )

    @staticmethod
    async def ensure_guild_exists(guild_id: int) -> Guild:
        """Ensure a guild exists in the database.

        Args:
            guild_id: The Discord guild ID

        Returns:
            Guild: The guild document
        """
        guild = db.get_document(Guild, guild_id)
        if not guild:
            guild = Guild(_id=guild_id)
            db.add_document(guild)
        return guild

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        """Handle bot joining a new guild.

        Args:
            guild: The Discord guild that was joined
        """
        self.logger.info(f"Joined guild: {guild.name} ({guild.id})")
        await self.ensure_guild_exists(guild.id)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild) -> None:
        """Handle bot leaving a guild.

        Args:
            guild: The Discord guild that was left
        """
        self.logger.info(f"Left guild: {guild.name} ({guild.id})")


async def setup(bot: commands.Bot) -> None:
    """Set up the GuildHandler cog.

    Args:
        bot: The Discord bot instance
    """
    await bot.add_cog(GuildHandlerCog(bot))

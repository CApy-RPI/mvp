import discord
import logging
from discord.ext import commands
from frontend.utils import colors
from config import settings


class ClearInteractionsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = logging.getLogger(
            f"discord.cog.{self.__class__.__name__.lower()}"
        )

    @commands.command(name="clear_interactions")
    @commands.is_owner()
    async def clear_interactions(self, ctx: commands.Context):
        try:
            self.logger.info("Clearing all application commands...")
            # Clear commands from all guilds
            for guild in self.bot.guilds:
                self.bot.tree.clear_commands(guild=guild)
            # Clear global commands
            self.bot.tree.clear_commands(guild=None)

            # Sync the empty tree
            debug_guild = self.get_guild(settings.DEBUG_GUILD_ID)
            if debug_guild:
                self.logger.info(f"Connected to debug guild: {debug_guild.name}")
            await self.tree.sync(guild=debug_guild)

            embed = discord.Embed(
                title="Clear Interactions",
                description="✅ Successfully cleared and re-synced all application commands!",
                color=colors.SUCCESS,
            )
            await ctx.send(embed=embed)

        except Exception as e:
            self.logger.error(f"Failed to clear interactions: {str(e)}")
            embed = discord.Embed(
                title="Clear Interactions",
                description=f"❌ Failed to clear interactions: {str(e)}",
                color=colors.ERROR,
            )
            await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(ClearInteractionsCog(bot))

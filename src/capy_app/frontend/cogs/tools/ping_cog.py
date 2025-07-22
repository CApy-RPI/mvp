import discord
import logging
from discord.ext import commands
from discord import app_commands

from frontend import config_colors as colors
from config import settings


class PingCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = logging.getLogger(
            f"discord.cog.{self.__class__.__name__.lower()}"
        )

    @app_commands.guilds(discord.Object(id=settings.DEBUG_GUILD_ID))
    @app_commands.command(name="ping", description="Shows the bot's latency")
    async def ping(self, interaction: discord.Interaction):
        message = f"⏱ {round(self.bot.latency * 1000)} ms Latency!"
        embed = discord.Embed(
            title="Ping",
            description=message,
            color=colors.PING,
        )
        self.logger.info(message)
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(PingCog(bot))

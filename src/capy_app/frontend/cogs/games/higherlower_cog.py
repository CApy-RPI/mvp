import logging
import random

import discord
from discord import app_commands
from discord.ext import commands

from config import settings


class HigherLowerCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = logging.getLogger(f"discord.cog.{self.__class__.__name__.lower()}")

    @app_commands.guilds(discord.Object(id=settings.DEBUG_GUILD_ID))
    @app_commands.command(
        name="higherlower",
        description="Picks a random number between user specified bounds that you have to guess",
    )
    async def higherlower(self, interaction: discord.Interaction, lower_bound: int, upper_bound: int):
        """Higher/Lower guessing game."""
        if lower_bound > upper_bound:
            await interaction.response.send_message("❌ Lower bound must be <= upper bound", ephemeral=True)
            return

        target = random.randint(lower_bound, upper_bound)
        self.logger.info(f"[HigherLower] Target number: {target}")

        await interaction.response.send_message(
            f"🎯 I've picked a number between {lower_bound} and {upper_bound}. Try to guess it!",
            ephemeral=True,
        )

        def check(msg: discord.Message):
            return msg.author == interaction.user and msg.channel == interaction.channel and msg.content.isdigit()

        while True:
            try:
                guess_msg = await self.bot.wait_for("message", check=check, timeout=120.0)
                guess = int(guess_msg.content)

                if guess < target:
                    await interaction.followup.send("🔽 Too low! Try again...", ephemeral=True)
                elif guess > target:
                    await interaction.followup.send("🔼 Too high! Try again...", ephemeral=True)
                else:
                    await interaction.followup.send(f"✅ You got it! The number was **{target}** 🎉", ephemeral=True)
                    break
            except TimeoutError:
                await interaction.followup.send("⌛ You took too long to respond. Game over!", ephemeral=True)
                break


async def setup(bot: commands.Bot):
    await bot.add_cog(HigherLowerCog(bot))

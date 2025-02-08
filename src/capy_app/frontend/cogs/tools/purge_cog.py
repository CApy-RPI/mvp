import discord
import logging
from discord.ext import commands
from discord import app_commands
from frontend.utils import colors


class PurgeCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = logging.getLogger(
            f"discord.cog.{self.__class__.__name__.lower()}"
        )

    @app_commands.command(
        name="purge", description="Delete a specified number of messages"
    )
    @app_commands.checks.has_permissions(manage_messages=True)
    async def purge(self, interaction: discord.Interaction, amount: int):
        if amount <= 0:
            embed = discord.Embed(
                title="Error",
                description="Please specify a number greater than 0",
                color=colors.ERROR,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        try:
            deleted = await interaction.channel.purge(limit=amount)
            message = f"✨ Successfully deleted {len(deleted)} messages!"
            embed = discord.Embed(
                title="Purge", description=message, color=colors.SUCCESS
            )
            self.logger.info(
                f"{interaction.user} purged {len(deleted)} messages in {interaction.channel}"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

        except discord.Forbidden:
            embed = discord.Embed(
                title="Error",
                description="I don't have permission to delete messages",
                color=colors.ERROR,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @commands.command(name="purge", help="Delete a specified number of messages")
    @commands.has_permissions(manage_messages=True)
    async def purge_prefix(self, ctx: commands.Context, amount: int):
        if amount <= 0:
            embed = discord.Embed(
                title="Error",
                description="Please specify a number greater than 0",
                color=colors.ERROR,
            )
            await ctx.send(embed=embed)
            return

        try:
            deleted = await ctx.channel.purge(limit=amount)
            message = f"✨ Successfully deleted {len(deleted)} messages!"
            embed = discord.Embed(
                title="Purge", description=message, color=colors.SUCCESS
            )
            self.logger.info(
                f"{ctx.author} purged {len(deleted)} messages in {ctx.channel}"
            )
            await ctx.send(embed=embed, delete_after=5)

        except discord.Forbidden:
            embed = discord.Embed(
                title="Error",
                description="I don't have permission to delete messages",
                color=colors.ERROR,
            )
            await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(PurgeCog(bot))

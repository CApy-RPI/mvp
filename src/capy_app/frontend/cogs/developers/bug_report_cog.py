"""Bug report command cog.

This module handles bug report submissions through a modal interface.
Reports are sent to a designated channel for developer review.
"""

import logging
import discord
from discord import app_commands
from discord.ext import commands

from config import settings
from frontend.config_colors import (
    STATUS_ERROR,
    STATUS_IMPORTANT,
    STATUS_RESOLVED,
    STATUS_IGNORED,
)


class BugReportModal(discord.ui.Modal, title="Report a Bug"):
    title = discord.ui.TextInput(
        label="Bug Title",
        placeholder="Brief description of the bug",
        required=True,
        max_length=100,
    )
    description = discord.ui.TextInput(
        label="Bug Description",
        placeholder="Please provide detailed steps to reproduce the bug...",
        required=True,
        style=discord.TextStyle.paragraph,
        max_length=1000,
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        self.interaction = interaction


class BugReportCog(commands.Cog):
    """Cog for handling bug report submissions."""

    def __init__(self, bot: commands.Bot) -> None:
        """Initialize the bug report cog.

        Args:
            bot: The Discord bot instance
        """
        self.bot = bot
        self.logger = logging.getLogger(
            f"discord.cog.{self.__class__.__name__.lower()}"
        )
        self.status_emojis = {
            "⭐": "Important",
            "✅": "Resolved",
            "❌": "Ignored",
            "🔄": "Unmarked",
        }

    @app_commands.guilds(discord.Object(id=settings.DEBUG_GUILD_ID))
    @app_commands.command(name="bug", description="Report a bug in the bot")
    async def bug(self, interaction: discord.Interaction) -> None:
        """Handle bug report command.

        Args:
            interaction: The Discord interaction instance
        """
        try:
            modal = BugReportModal()
            await interaction.response.send_modal(modal)

            try:
                await modal.wait()
            except TimeoutError:
                self.logger.warning(
                    f"Bug report timed out from user {interaction.user.id}"
                )
                # Don't try to send a followup for timeout
                return

            if not modal.title or not modal.description:
                self.logger.warning(
                    f"Bug report missing required fields from user {interaction.user.id}"
                )
                # Modal was closed without submission
                return

            channel = self.bot.get_channel(settings.TICKET_BUG_REPORT_CHANNEL_ID)
            if not channel:
                self.logger.error("Bug report channel not found")
                await interaction.followup.send(
                    "❌ Bug report channel not configured. Please contact an administrator.",
                    ephemeral=True,
                )
                return

            embed = discord.Embed(
                title=f"🐛 Bug Report:",
                description=modal.description,
                color=STATUS_ERROR,
            )
            embed.add_field(name="Submitted by", value=interaction.user.mention)
            embed.set_footer(
                text="Status: Unmarked | ⭐ Important • ✅ Resolve • ❌ Ignore • 🔄 Reset"
            )

            message = await channel.send(embed=embed)
            for emoji in self.status_emojis.keys():
                await message.add_reaction(emoji)

            await interaction.followup.send(
                "Bug report submitted successfully!", ephemeral=True
            )
            self.logger.info(
                f"Bug report '{modal.title}' submitted by user {interaction.user.id}"
            )

        except discord.HTTPException as e:
            self.logger.error(f"HTTP error processing bug report: {str(e)}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ Failed to submit bug report. Please try again later.",
                    ephemeral=True,
                )

        except Exception as e:
            self.logger.error(f"Error processing bug report: {str(e)}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ An unexpected error occurred. Please try again later.",
                    ephemeral=True,
                )

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.channel_id != settings.TICKET_BUG_REPORT_CHANNEL_ID:
            return

        if payload.user_id == self.bot.user.id:  # Ignore bot's own reactions
            return

        channel = self.bot.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)

        if not message.embeds or not message.embeds[0].title.startswith(
            "🐛 Bug Report:"
        ):
            return

        emoji = str(payload.emoji)
        if emoji not in self.status_emojis:
            return

        # Remove the user's reaction immediately
        await message.remove_reaction(payload.emoji, payload.member)

        embed = message.embeds[0]
        status = self.status_emojis[emoji]

        if status == "Unmarked":
            embed.color = STATUS_ERROR
        else:
            embed.color = {
                "Important": STATUS_IMPORTANT,
                "Resolved": STATUS_RESOLVED,
                "Ignored": STATUS_IGNORED,
            }[status]

        embed.set_footer(
            text=f"Status: {status} | ⭐ Important • ✅ Resolve • ❌ Ignore • 🔄 Reset"
        )
        await message.edit(embed=embed)


async def setup(bot: commands.Bot) -> None:
    """Set up the Bug Report cog."""
    await bot.add_cog(BugReportCog(bot))

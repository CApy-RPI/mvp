"""Feedback command cog.

This module handles feedback submissions through a modal interface.
Feedback is sent to a designated channel for developer review.
"""

import logging
import discord
from discord import app_commands
from discord.ext import commands

from config import settings
from .request_modal import RequestModal
from frontend.config_colors import TICKET_FEATURE, TICKET_FEEDBACK


class FeedbackCog(commands.Cog):
    """Cog for handling feedback submissions."""

    def __init__(self, bot: commands.Bot) -> None:
        """Initialize the feedback cog.

        Args:
            bot: The Discord bot instance
        """
        self.bot = bot
        self.logger = logging.getLogger(
            f"discord.cog.{self.__class__.__name__.lower()}"
        )

    @app_commands.guilds(discord.Object(id=settings.DEBUG_GUILD_ID))
    @app_commands.command(name="feedback", description="Provide general feedback")
    async def feedback(self, interaction: discord.Interaction) -> None:
        """Handle feedback command.

        Args:
            interaction: The Discord interaction instance
        """
        try:
            modal = RequestModal("Feedback", "Please provide your feedback...")
            await interaction.response.send_modal(modal)

            try:
                await modal.wait()
            except TimeoutError:
                self.logger.warning(
                    f"Feedback timed out from user {interaction.user.id}"
                )
                return

            if not modal.title or not modal.description:
                self.logger.warning(
                    f"Feedback missing required fields from user {interaction.user.id}"
                )
                return

            channel = self.bot.get_channel(settings.TICKET_FEEDBACK_CHANNEL_ID)
            if not channel:
                self.logger.error("Feedback channel not found")
                await interaction.followup.send(
                    "❌ Feedback channel not configured. Please contact an administrator.",
                    ephemeral=True,
                )
                return

            embed = discord.Embed(
                title=f"📝 Feedback: {modal.title}",
                description=modal.description,
                color=TICKET_FEEDBACK,
            )
            embed.add_field(name="Submitted by", value=interaction.user.mention)
            embed.set_footer(text=f"User ID: {interaction.user.id}")

            await channel.send(embed=embed)
            await interaction.followup.send(
                "Feedback submitted successfully!", ephemeral=True
            )
            self.logger.info(
                f"Feedback '{modal.title}' submitted by user {interaction.user.id}"
            )

        except discord.HTTPException as e:
            self.logger.error(f"HTTP error processing feedback: {str(e)}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ Failed to submit feedback. Please try again later.",
                    ephemeral=True,
                )

        except Exception as e:
            self.logger.error(f"Error processing feedback: {str(e)}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ An unexpected error occurred. Please try again later.",
                    ephemeral=True,
                )


async def setup(bot: commands.Bot) -> None:
    """Set up the Feedback cog."""
    await bot.add_cog(FeedbackCog(bot))

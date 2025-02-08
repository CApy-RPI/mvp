"""Feature request command cog.

This module handles feature request submissions through a modal interface.
Requests are sent to a designated channel for developer review.
"""

import logging
import discord
from discord import app_commands
from discord.ext import commands

from config import settings
from .request_modal import RequestModal
from frontend.config_colors import TICKET_FEATURE


class FeatureRequestCog(commands.Cog):
    """Cog for handling feature request submissions."""

    def __init__(self, bot: commands.Bot) -> None:
        """Initialize the feature request cog.

        Args:
            bot: The Discord bot instance
        """
        self.bot = bot
        self.logger = logging.getLogger(
            f"discord.cog.{self.__class__.__name__.lower()}"
        )

    @app_commands.guilds(discord.Object(id=settings.DEBUG_GUILD_ID))
    @app_commands.command(name="feature", description="Request a new feature")
    async def feature(self, interaction: discord.Interaction) -> None:
        """Handle feature request command.

        Args:
            interaction: The Discord interaction instance
        """
        try:
            modal = RequestModal(
                "Feature Request", "Please describe the feature you'd like to see..."
            )
            await interaction.response.send_modal(modal)

            try:
                await modal.wait()
            except TimeoutError:
                self.logger.warning(
                    f"Feature request timed out from user {interaction.user.id}"
                )
                return

            if not modal.title or not modal.description:
                self.logger.warning(
                    f"Feature request missing required fields from user {interaction.user.id}"
                )
                return

            channel = self.bot.get_channel(settings.TICKET_FEATURE_REQUEST_CHANNEL_ID)
            if not channel:
                self.logger.error("Feature request channel not found")
                await interaction.followup.send(
                    "❌ Feature request channel not configured. Please contact an administrator.",
                    ephemeral=True,
                )
                return

            embed = discord.Embed(
                title=f"💡 Feature Request: {modal.title}",
                description=modal.description,
                color=TICKET_FEATURE,
            )
            embed.add_field(name="Submitted by", value=interaction.user.mention)
            embed.set_footer(text=f"User ID: {interaction.user.id}")

            await channel.send(embed=embed)
            await interaction.followup.send(
                "Feature request submitted successfully!", ephemeral=True
            )
            self.logger.info(
                f"Feature request '{modal.title}' submitted by user {interaction.user.id}"
            )

        except discord.HTTPException as e:
            self.logger.error(f"HTTP error processing feature request: {str(e)}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ Failed to submit feature request. Please try again later.",
                    ephemeral=True,
                )

        except Exception as e:
            self.logger.error(f"Error processing feature request: {str(e)}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ An unexpected error occurred. Please try again later.",
                    ephemeral=True,
                )


async def setup(bot: commands.Bot) -> None:
    """Set up the Feature Request cog."""
    await bot.add_cog(FeatureRequestCog(bot))

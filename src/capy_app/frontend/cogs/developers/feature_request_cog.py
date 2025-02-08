"""Feature request command cog.

This module handles feature request submissions through a modal interface.
Requests are sent to a designated channel for developer review.
"""

import logging
import discord
from discord import app_commands
from discord.ext import commands

from config import settings
from frontend.config_colors import (
    STATUS_UNMARKED,
    STATUS_RESOLVED,
    STATUS_IMPORTANT,
    STATUS_IGNORED,
)


class FeatureRequestModal(discord.ui.Modal, title="Request a Feature"):
    title = discord.ui.TextInput(
        label="Feature Title",
        placeholder="Brief description of the feature",
        required=True,
        max_length=100,
    )
    description = discord.ui.TextInput(
        label="Feature Description",
        placeholder="Please describe the feature you'd like to see in detail...",
        required=True,
        style=discord.TextStyle.paragraph,
        max_length=1000,
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        self.interaction = interaction


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
        self.status_emojis = {
            "✅": "Completed",
            "👍": "Approved",
            "❌": "Ignored",
            "🔄": "Unmarked",
        }

    @app_commands.guilds(discord.Object(id=settings.DEBUG_GUILD_ID))
    @app_commands.command(name="feature", description="Request a new feature")
    async def feature(self, interaction: discord.Interaction) -> None:
        """Handle feature request command.

        Args:
            interaction: The Discord interaction instance
        """
        try:
            modal = FeatureRequestModal()
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
                title=f"💡 Feature Request:",
                description=modal.description,
                color=STATUS_UNMARKED,
            )
            embed.add_field(name="Submitted by", value=interaction.user.mention)
            embed.set_footer(
                text="Status: Unmarked | ✅ Complete • 👍 Approve • ❌ Ignore • 🔄 Reset"
            )

            message = await channel.send(embed=embed)
            for emoji in self.status_emojis.keys():
                await message.add_reaction(emoji)

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

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.channel_id != settings.TICKET_FEATURE_REQUEST_CHANNEL_ID:
            return

        if payload.user_id == self.bot.user.id:  # Ignore bot's own reactions
            return

        channel = self.bot.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)

        if not message.embeds or not message.embeds[0].title.startswith(
            "💡 Feature Request:"
        ):
            return

        emoji = str(payload.emoji)
        if emoji not in self.status_emojis:
            return

        embed = message.embeds[0]
        status = self.status_emojis[emoji]

        if status == "Unmarked":
            embed.color = STATUS_UNMARKED
        else:
            embed.color = {
                "Completed": STATUS_RESOLVED,
                "Approved": STATUS_IMPORTANT,
                "Ignored": STATUS_IGNORED,
            }[status]

        embed.set_footer(
            text=f"Status: {status} | ✅ Complete • 👍 Approve • ❌ Ignore • 🔄 Reset"
        )
        await message.edit(embed=embed)


async def setup(bot: commands.Bot) -> None:
    """Set up the Feature Request cog."""
    await bot.add_cog(FeatureRequestCog(bot))

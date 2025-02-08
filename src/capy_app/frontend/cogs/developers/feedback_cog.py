"""Feedback command cog.

This module handles feedback submissions through a modal interface.
Feedback is sent to a designated channel for developer review.
"""

import logging
import discord
from discord import app_commands
from discord.ext import commands

from config import settings
from frontend.config_colors import (
    STATUS_INFO,
    STATUS_RESOLVED,
    STATUS_IGNORED,
)


class FeedbackModal(discord.ui.Modal, title="Submit Feedback"):
    title = discord.ui.TextInput(
        label="Feedback Title",
        placeholder="Brief summary of your feedback",
        required=True,
        max_length=100,
    )
    description = discord.ui.TextInput(
        label="Feedback Description",
        placeholder="Please provide your detailed feedback...",
        required=True,
        style=discord.TextStyle.paragraph,
        max_length=1000,
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        self.interaction = interaction


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
        self.status_emojis = {"✅": "Acknowledged", "❌": "Ignored"}

    @app_commands.guilds(discord.Object(id=settings.DEBUG_GUILD_ID))
    @app_commands.command(name="feedback", description="Provide general feedback")
    async def feedback(self, interaction: discord.Interaction) -> None:
        """Handle feedback command.

        Args:
            interaction: The Discord interaction instance
        """
        try:
            modal = FeedbackModal()
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
                color=STATUS_INFO,
            )
            embed.add_field(name="Submitted by", value=interaction.user.mention)
            embed.set_footer(text="Status: Unmarked | ✅ Acknowledged • ❌ Ignored")

            message = await channel.send(embed=embed)
            for emoji in self.status_emojis.keys():
                await message.add_reaction(emoji)

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

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.channel_id != settings.TICKET_FEEDBACK_CHANNEL_ID:
            return

        if payload.user_id == self.bot.user.id:  # Ignore bot's own reactions
            return

        channel = self.bot.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)

        if not message.embeds or not message.embeds[0].title.startswith("📝 Feedback:"):
            return

        emoji = str(payload.emoji)
        if emoji not in self.status_emojis:
            return

        embed = message.embeds[0]
        status = self.status_emojis[emoji]

        embed.color = {
            "Acknowledged": STATUS_RESOLVED,
            "Ignored": STATUS_IGNORED,
        }[status]

        embed.set_footer(text=f"Status: {status} | ✅ Acknowledged • ❌ Ignored")
        await message.edit(embed=embed)


async def setup(bot: commands.Bot) -> None:
    """Set up the Feedback cog."""
    await bot.add_cog(FeedbackCog(bot))

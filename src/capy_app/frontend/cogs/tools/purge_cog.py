"""Message purging functionality for server management.

This module provides commands for bulk message deletion with various modes.

#TODO: Add audit logging for purge actions
#TODO: Separate purge command into subcommands like guild or profile
#! Use with caution - deletions are permanent
"""

import logging
import typing
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
import re

from frontend.utils.embed_statuses import success_embed, error_embed
from config import settings


class DateTimeModal(discord.ui.Modal, title="Enter Date and Time"):
    """Modal for date and time input."""

    def __init__(self) -> None:
        """Initialize the date time modal."""
        super().__init__()
        self.add_item(
            discord.ui.TextInput(
                label="Date (YYYY-MM-DD)",
                placeholder="2024-02-08",
                required=True,
            )
        )
        self.add_item(
            discord.ui.TextInput(
                label="Time (HH:MM)",
                placeholder="14:30",
                required=True,
            )
        )


class PurgeModeView(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.mode: typing.Optional[str] = None
        self.value: typing.Union[int, str, datetime, None] = None

        self.mode_select: discord.ui.Select = discord.ui.Select(
            placeholder="Choose purge mode",
            options=[
                discord.SelectOption(
                    label="Message Count",
                    value="count",
                    description="Delete specific number of messages",
                ),
                discord.SelectOption(
                    label="Time Duration",
                    value="duration",
                    description="Delete messages from last X time",
                ),
                discord.SelectOption(
                    label="Specific Date",
                    value="date",
                    description="Delete messages since specific date/time",
                ),
            ],
        )

        async def mode_callback(interaction: discord.Interaction) -> None:
            self.mode = self.mode_select.values[0]
            if self.mode == "count":
                modal = discord.ui.Modal(title="Enter Count")
                text_input = discord.ui.TextInput(
                    label="Number of messages", placeholder="10"
                )
                modal.add_item(text_input)

                async def count_callback(interaction: discord.Interaction) -> None:
                    self.value = int(text_input.value)
                    await interaction.response.defer()
                    self.stop()

                modal.on_submit = count_callback
                await interaction.response.send_modal(modal)

            elif self.mode == "duration":
                modal = discord.ui.Modal(title="Enter Duration")
                text_input = discord.ui.TextInput(
                    label="Duration (1d2h3m)",
                    placeholder="1d = 1 day, 2h = 2 hours, 3m = 3 minutes",
                )
                modal.add_item(text_input)

                async def duration_callback(interaction: discord.Interaction) -> None:
                    self.value = text_input.value
                    await interaction.response.defer()
                    self.stop()

                modal.on_submit = duration_callback
                await interaction.response.send_modal(modal)

            elif self.mode == "date":
                modal = DateTimeModal()

                async def date_callback(interaction: discord.Interaction) -> None:
                    try:
                        date_input = modal.children[0]
                        time_input = modal.children[1]
                        if isinstance(date_input, discord.ui.TextInput) and isinstance(
                            time_input, discord.ui.TextInput
                        ):
                            self.value = datetime.strptime(
                                f"{date_input.value} {time_input.value}",
                                "%Y-%m-%d %H:%M",
                            )
                        await interaction.response.defer()
                        self.stop()
                    except ValueError:
                        await interaction.response.send_message(
                            "Invalid date/time format", ephemeral=True
                        )

                modal.on_submit = date_callback
                await interaction.response.send_modal(modal)

        self.mode_select.callback = mode_callback
        self.add_item(self.mode_select)


class PurgeCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = logging.getLogger(
            f"discord.cog.{self.__class__.__name__.lower()}"
        )

    def parse_duration(self, duration: str) -> timedelta | None:
        """Parse duration string into timedelta. Format: 1d2h3m"""
        if not duration:
            return None

        pattern = r"(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)m)?"
        match = re.match(pattern, duration)
        if not match or not any(match.groups()):
            return None

        days = int(match.group(1) or 0)
        hours = int(match.group(2) or 0)
        minutes = int(match.group(3) or 0)

        return timedelta(days=days, hours=hours, minutes=minutes)

    async def _handle_purge_count(self, amount: int, channel: discord.TextChannel):
        if amount <= 0:
            return False, "Please specify a number greater than 0"
        deleted = await channel.purge(limit=amount)
        return True, f"✨ Successfully deleted {len(deleted)} messages!"

    async def _handle_purge_duration(self, duration: str, channel: discord.TextChannel):
        time_delta = self.parse_duration(duration)
        if not time_delta:
            return (
                False,
                "Invalid duration format. Use format: 1d2h3m (e.g., 1d = 1 day, 2h = 2 hours, 3m = 3 minutes)",
            )

        after_time = datetime.utcnow() - time_delta
        deleted = await channel.purge(after=after_time)
        return (
            True,
            f"✨ Successfully deleted {len(deleted)} messages from the last {duration}!",
        )

    async def _handle_purge_date(self, date: datetime, channel: discord.TextChannel):
        if date > datetime.utcnow():
            return False, "Cannot purge future messages"
        deleted = await channel.purge(after=date)
        return (
            True,
            f"✨ Successfully deleted {len(deleted)} messages since {date.strftime('%Y-%m-%d %H:%M')}!",
        )

    @app_commands.guilds(discord.Object(id=settings.DEBUG_GUILD_ID))
    @app_commands.command(name="purge", description="Delete messages")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def purge(self, interaction: discord.Interaction) -> None:
        view = PurgeModeView()
        await interaction.response.send_message(
            "Select purge mode:", view=view, ephemeral=True
        )

        await view.wait()
        if not view.mode or not view.value:
            await interaction.followup.send(
                "Purge cancelled or timed out.", ephemeral=True
            )
            return

        try:
            if isinstance(interaction.channel, discord.TextChannel):
                if view.mode == "count" and isinstance(view.value, int):
                    success, message = await self._handle_purge_count(
                        view.value, interaction.channel
                    )
                elif view.mode == "duration" and isinstance(view.value, str):
                    success, message = await self._handle_purge_duration(
                        view.value, interaction.channel
                    )
                elif view.mode == "date" and isinstance(view.value, datetime):
                    success, message = await self._handle_purge_date(
                        view.value, interaction.channel
                    )

            embed = (
                success_embed("Purge", message)
                if success
                else error_embed("Error", message)
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

            if success:
                self.logger.info(
                    f"{interaction.user} purged messages in {interaction.channel} using {view.mode} mode"
                )

        except discord.Forbidden:
            await interaction.followup.send(
                embed=error_embed(
                    "Error", "I don't have permission to delete messages"
                ),
                ephemeral=True,
            )
        except Exception as e:
            await interaction.followup.send(
                embed=error_embed("Error", f"An error occurred: {str(e)}"),
                ephemeral=True,
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(PurgeCog(bot))

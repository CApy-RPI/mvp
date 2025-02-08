import discord
import logging
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
import re

from frontend.utils.embed_helpers import success_embed, error_embed
from config import settings


class DateTimeModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Enter Date and Time")
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
        self.mode = None
        self.value = None

        mode_select = discord.ui.Select(
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

        async def mode_callback(interaction: discord.Interaction):
            self.mode = mode_select.values[0]
            if self.mode == "count":
                modal = discord.ui.Modal(title="Enter Count")
                modal.add_item(
                    discord.ui.TextInput(label="Number of messages", placeholder="10")
                )

                async def count_callback(interaction: discord.Interaction):
                    self.value = int(modal.children[0].value)
                    await interaction.response.defer()
                    self.stop()

                modal.on_submit = count_callback
                await interaction.response.send_modal(modal)

            elif self.mode == "duration":
                modal = discord.ui.Modal(title="Enter Duration")
                modal.add_item(
                    discord.ui.TextInput(
                        label="Duration (1d2h3m)",
                        placeholder="1d = 1 day, 2h = 2 hours, 3m = 3 minutes",
                    )
                )

                async def duration_callback(interaction: discord.Interaction):
                    self.value = modal.children[0].value
                    await interaction.response.defer()
                    self.stop()

                modal.on_submit = duration_callback
                await interaction.response.send_modal(modal)

            elif self.mode == "date":
                modal = DateTimeModal()

                async def date_callback(interaction: discord.Interaction):
                    try:
                        date_str = modal.children[0].value
                        time_str = modal.children[1].value
                        self.value = datetime.strptime(
                            f"{date_str} {time_str}", "%Y-%m-%d %H:%M"
                        )
                        await interaction.response.defer()
                        self.stop()
                    except ValueError:
                        await interaction.response.send_message(
                            "Invalid date/time format", ephemeral=True
                        )

                modal.on_submit = date_callback
                await interaction.response.send_modal(modal)

        mode_select.callback = mode_callback
        self.add_item(mode_select)


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
    async def purge(self, interaction: discord.Interaction):
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
            if view.mode == "count":
                success, message = await self._handle_purge_count(
                    view.value, interaction.channel
                )
            elif view.mode == "duration":
                success, message = await self._handle_purge_duration(
                    view.value, interaction.channel
                )
            elif view.mode == "date":
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

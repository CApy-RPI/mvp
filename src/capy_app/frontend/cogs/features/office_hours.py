import discord
import logging
from discord.ext import commands
from discord import app_commands
from typing import Dict, List, Optional, cast

from frontend.interactions.bases.modal_base import ButtonDynamicModalView
from frontend.interactions.bases.dropdown_base import DynamicDropdownView
from backend.db.documents.guild import Guild, OfficeHours  # Add OfficeHours import
from config import settings
from frontend import config_colors as colors

TIME_SLOTS = [
    "8:00 AM",
    "9:00 AM",
    "10:00 AM",
    "11:00 AM",
    "12:00 PM",
    "1:00 PM",
    "2:00 PM",
    "3:00 PM",
    "4:00 PM",
    "5:00 PM",
    "6:00 PM",
    "7:00 PM",
    "8:00 PM",
    "9:00 PM",
    "10:00 PM",
    "11:00 PM",
]

WEEKDAYS = [
    "Sunday",
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
]


class OfficeHoursCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @app_commands.guilds(discord.Object(id=settings.DEBUG_GUILD_ID))
    @app_commands.command(name="officehours", description="Set your office hours")
    async def office_hours(self, interaction: discord.Interaction):
        # First collect name via modal
        name_modal = ButtonDynamicModalView(
            modal={
                "title": "Office Hours Setup",
                "fields": [
                    {
                        "label": "Name",
                        "placeholder": "Your display name",
                        "required": True,
                    }
                ],
            }
        )

        values, msg = await name_modal.initiate_from_interaction(interaction)
        if not values:
            return

        name = values["name"]
        schedule: Dict[str, List[str]] = {}

        # Show one dropdown per day
        msg = await interaction.original_response()
        for day in WEEKDAYS:
            dropdown = DynamicDropdownView(
                dropdowns=[
                    {
                        "placeholder": f"Select time for {day}",
                        "selections": [
                            {"label": time, "value": time} for time in TIME_SLOTS
                        ],
                        "min_values": 0,
                        "max_values": 1,  # Only allow one selection per day
                        "custom_id": "time_select",  # Single dropdown, fixed ID is fine
                    }
                ]
            )

            selections, msg = await dropdown.initiate_from_message(
                msg, content=f"Select office hours time for {day}:"
            )
            if not selections:
                return

            times = selections.get("time_select", [])
            schedule[day] = times

        # Store in database
        guild = Guild.objects(_id=interaction.guild_id).first()
        if not guild:
            await interaction.followup.send(
                "Error: Guild not configured", ephemeral=True
            )
            return

        # Remove existing schedule for this user
        guild.update(pull__office_hours__name=name)
        # Add new schedule
        guild.update(push__office_hours={"name": name, "schedule": schedule})

        # Show the schedule
        embed = self.generate_office_hours_embed(name, schedule)
        await interaction.followup.send(
            content="Office hours schedule set!", embed=embed, ephemeral=True
        )

    def generate_office_hours_embed(
        self, name: str, schedule: Dict[str, List[str]]
    ) -> discord.Embed:
        embed = discord.Embed(title=f"Office Hours - {name}", color=colors.SUCCESS)

        for day, times in schedule.items():
            if times:
                embed.add_field(name=day, value="\n".join(times), inline=True)
            else:
                embed.add_field(name=day, value="No office hours", inline=True)

        return embed

    def generate_weekly_schedule_embed(
        self, schedules: List[OfficeHours]  # Now OfficeHours is defined
    ) -> discord.Embed:
        """Generate a combined weekly schedule showing all office hours."""
        embed = discord.Embed(
            title="Weekly Office Hours Schedule", color=colors.SUCCESS
        )

        # Create schedule for each day
        for day in [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]:
            daily_schedule = []
            for person in schedules:
                times = person.schedule.get(day, [])
                if times:
                    times_str = ", ".join(times)
                    daily_schedule.append(f"{person.name}: {times_str}")

            value = "\n".join(daily_schedule) if daily_schedule else "No office hours"
            embed.add_field(name=day, value=value, inline=False)

        return embed

    @app_commands.guilds(discord.Object(id=settings.DEBUG_GUILD_ID))
    @app_commands.command(
        name="schedule", description="View combined weekly office hours schedule"
    )
    async def weekly_schedule(self, interaction: discord.Interaction):
        """Display the combined weekly office hours schedule."""
        guild = Guild.objects(_id=interaction.guild_id).first()
        if not guild or not guild.office_hours:
            await interaction.response.send_message(
                "No office hours schedules found", ephemeral=True
            )
            return

        embed = self.generate_weekly_schedule_embed(guild.office_hours)
        await interaction.response.send_message(embed=embed)

    @app_commands.guilds(discord.Object(id=settings.DEBUG_GUILD_ID))
    @app_commands.command(name="viewhours", description="View office hours schedule")
    async def view_hours(self, interaction: discord.Interaction):
        guild = Guild.objects(_id=interaction.guild_id).first()
        if not guild or not guild.office_hours:
            await interaction.response.send_message(
                "No office hours schedules found", ephemeral=True
            )
            return

        embeds = []
        for oh in guild.office_hours:
            embed = self.generate_office_hours_embed(oh.name, oh.schedule)
            embeds.append(embed)

        await interaction.response.send_message(embeds=embeds, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(OfficeHoursCog(bot))

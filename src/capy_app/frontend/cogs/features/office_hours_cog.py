# mypy: ignore-errors
# flake8: noqa
# TODO Remove on rewrite ^

import discord
import logging
from discord.ext import commands
from discord import app_commands
from typing import Dict, List, Optional
from frontend.interactions.bases.modal_base import DynamicModalView
from frontend.interactions.bases.dropdown_base import DynamicDropdownView
from backend.db.documents.guild import Guild, OfficeHours
from backend.db.database import Database
from config import settings
from frontend import config_colors as colors
from frontend.cogs.features.office_hours_config import PROFILE_CONFIG

# TIME_SLOTS = [
#     "8:00 AM",
#     "9:00 AM",
#     "10:00 AM",
#     "11:00 AM",
#     "12:00 PM",
#     "1:00 PM",
#     "2:00 PM",
#     "3:00 PM",
#     "4:00 PM",
#     "5:00 PM",
#     "6:00 PM",
#     "7:00 PM",
#     "8:00 PM",
#     "9:00 PM",
#     "10:00 PM",
#     "11:00 PM",
# ]

# WEEKDAY_GROUPS = [
#     ["Monday", "Tuesday", "Wednesday", "Thursday"],
#     ["Friday", "Saturday", "Sunday"],
# ]


# class OfficeHoursCog(commands.Cog):
#     def __init__(self, bot: commands.Bot):
#         self.bot = bot
#         self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

#     @app_commands.command(name="office_hours", description="Manage office hours")
#     @app_commands.guilds(discord.Object(id=settings.DEBUG_GUILD_ID))
#     @app_commands.choices(
#         action=[
#             app_commands.Choice(name="edit", value="edit"),
#             app_commands.Choice(name="show", value="show"),
#             app_commands.Choice(name="announce", value="announce"),
#             app_commands.Choice(name="clear", value="clear"),
#         ]
#     )
#     async def office_hours(
#         self,
#         interaction: discord.Interaction,
#         action: str,
#         user: Optional[discord.User] = None,
#     ):
#         """Manage office hours with a single command"""
#         guild = Database.get_document(Guild, interaction.guild_id)
#         if not guild:
#             await interaction.response.send_message(
#                 "Error: Guild not configured", ephemeral=True
#             )
#             return

#         if action == "edit":
#             await self._handle_edit(interaction, guild)
#         elif action == "clear":
#             await self._handle_clear(interaction, guild)
#         elif action in ["show", "announce"]:
#             await self._handle_display(
#                 interaction,
#                 guild,
#                 user or interaction.user,
#                 is_announcement=(action == "announce"),
#             )

#     async def _handle_edit(self, interaction: discord.Interaction, guild: Guild):
#         # Remove name modal and use user ID directly
#         user_id = str(interaction.user.id)
#         existing_schedule = None

#         # Check for existing schedule
#         if guild.office_hours:
#             existing = next(
#                 (oh for oh in guild.office_hours if oh.name == user_id), None
#             )
#             if existing:
#                 existing_schedule = existing.schedule

#         # Get configs with defaults if they exist
#         configs = get_office_hours_config(existing_schedule)

#         # Collect first half of week (Sun-Wed)
#         first_half = DynamicDropdownView(**configs["first_half_week"])
#         first_half_selections, msg = await first_half.initiate_from_interaction(
#             interaction, "Select office hours for Sunday through Wednesday:"
#         )

#         # Collect second half of week (Thu-Sat)
#         second_half = DynamicDropdownView(**configs["second_half_week"])
#         second_half_selections, msg = await second_half.initiate_from_message(
#             msg, "Select office hours for Thursday through Saturday:"
#         )

#         # Combine selections into schedule
#         schedule = {
#             **{
#                 day: first_half_selections.get(day, [])
#                 for day in ["sunday", "monday", "tuesday", "wednesday"]
#             },
#             **{
#                 day: second_half_selections.get(day, [])
#                 for day in ["thursday", "friday", "saturday"]
#             },
#         }

#         # Remove existing schedule and add new one
#         if guild.office_hours:
#             guild.office_hours = [oh for oh in guild.office_hours if oh.name != user_id]
#         guild.office_hours.append(OfficeHours(name=user_id, schedule=schedule))
#         Database.update_document(guild, {"office_hours": guild.office_hours})

#         # Show the schedule using display name
#         embed = self.generate_office_hours_embed(interaction.user, schedule)
#         await interaction.followup.send(
#             content="Office hours schedule set!", embed=embed, ephemeral=True
#         )

#     async def _handle_clear(self, interaction: discord.Interaction, guild: Guild):
#         user_id = str(interaction.user.id)
#         if guild.office_hours:
#             guild.office_hours = [oh for oh in guild.office_hours if oh.name != user_id]
#             Database.update_document(guild, {"office_hours": guild.office_hours})
#             await interaction.response.send_message(
#                 f"Cleared your office hours", ephemeral=True
#             )
#         else:
#             await interaction.response.send_message(
#                 "You don't have any office hours set", ephemeral=True
#             )

#     async def _handle_display(
#         self,
#         interaction: discord.Interaction,
#         guild: Guild,
#         user: discord.User,
#         is_announcement: bool = False,
#     ):
#         if not guild.office_hours:
#             await interaction.response.send_message(
#                 "No office hours schedules found", ephemeral=True
#             )
#             return

#         if is_announcement:
#             # For announcements, always show the weekly schedule
#             embed = self.generate_weekly_schedule_embed(guild.office_hours)
#             await interaction.response.send_message(embed=embed, ephemeral=False)
#             return

#         # For regular show command, show individual schedule
#         user_id = str(user.id)
#         schedule = next(
#             (oh for oh in guild.office_hours if oh.name == user_id),
#             None,
#         )

#         if not schedule:
#             msg = (
#                 "You don't have any office hours set"
#                 if user == interaction.user
#                 else f"{user.display_name} doesn't have any office hours set"
#             )
#             await interaction.response.send_message(msg, ephemeral=True)
#             return

#         embed = self.generate_office_hours_embed(user, schedule.schedule)
#         await interaction.response.send_message(embed=embed, ephemeral=True)

#     def generate_office_hours_embed(
#         self, user: discord.User, schedule: Dict[str, List[str]]
#     ) -> discord.Embed:
#         embed = discord.Embed(
#             title=f"Office Hours - {user.display_name}", color=colors.STATUS_SUCCESS
#         )

#         for day, times in schedule.items():
#             if times:
#                 embed.add_field(name=day, value="\n".join(times), inline=True)
#             else:
#                 embed.add_field(name=day, value="No office hours", inline=True)

#         return embed

#     def generate_weekly_schedule_embed(
#         self, schedules: List[OfficeHours]
#     ) -> discord.Embed:
#         """Generate a combined weekly schedule showing all office hours."""
#         embed = discord.Embed(
#             title="Weekly Office Hours Schedule", color=colors.STATUS_SUCCESS
#         )

#         days = [
#             "Monday",
#             "Tuesday",
#             "Wednesday",
#             "Thursday",
#             "Friday",
#             "Saturday",
#             "Sunday",
#         ]

#         # Create schedule for each day
#         for day in days:
#             daily_schedule = []
#             for oh in schedules:
#                 times = oh.schedule.get(day.lower(), [])
#                 if times:
#                     # Get user from ID and use their display name
#                     try:
#                         member = self.bot.get_user(int(oh.name))
#                         name = member.display_name if member else f"User{oh.name}"
#                     except (ValueError, AttributeError):
#                         name = f"User{oh.name}"

#                     times_str = ", ".join(times)
#                     daily_schedule.append(f"• **{name}**: {times_str}")

#             value = "\n".join(daily_schedule) if daily_schedule else "No office hours"
#             embed.add_field(name=day, value=value, inline=False)

#         return embed


# async def setup(bot: commands.Bot):
#     await bot.add_cog(OfficeHoursCog(bot))

class OfficeHoursCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        # Temporary storage for first-modal results awaiting second modal
        self._pending_schedules: Dict[str, Dict[str, str]] = {}

    @app_commands.command(name="office_hours", description="Manage office hours")
    @app_commands.guilds(discord.Object(id=settings.DEBUG_GUILD_ID))
    @app_commands.choices(
        action=[
            app_commands.Choice(name="edit", value="edit"),
            app_commands.Choice(name="show", value="show"),
            app_commands.Choice(name="announce", value="announce"),
            app_commands.Choice(name="clear", value="clear"),
        ]
    )
    async def office_hours(
        self,
        interaction: discord.Interaction,
        action: str,
        user: Optional[discord.User] = None,
    ):
        """Manage office hours with a single command"""
        guild = Database.get_document(Guild, interaction.guild_id)
        if not guild:
            await interaction.response.send_message(
                "Error: Guild not configured", ephemeral=True
            )
            return

        if action == "edit":
            await self._handle_edit(interaction, guild)
        elif action == "clear":
            await self._handle_clear(interaction, guild)
        elif action in ["show", "announce"]:
            await self._handle_display(
                interaction,
                guild,
                user or interaction.user,
                is_announcement=(action == "announce"),
            )

    async def _handle_edit(self, interaction: discord.Interaction, guild: Guild):
        user_id = str(interaction.user.id)
        existing_schedule = None

        if guild.office_hours:
            existing = next(
                (oh for oh in guild.office_hours if oh.name == user_id), None
            )
            if existing:
                existing_schedule = existing.schedule

        modal_config = PROFILE_CONFIG.get("office_hour_modal")
        if not modal_config:
            self.logger.error("Office hour modal config not found")
            await interaction.response.send_message(
                "Configuration error: cannot find office hours modal.", ephemeral=True
            )
            return

        full_fields = modal_config.get("modal", {}).get("fields", [])
        if not full_fields:
            self.logger.error("Office hour modal fields missing")
            await interaction.response.send_message(
                "Configuration error: office hours fields missing.", ephemeral=True
            )
            return

        split_index = min(5, len(full_fields))
        fields_part1 = full_fields[:split_index]
        fields_part2 = full_fields[split_index:]

        # First modal
        config1 = {
            "ephemeral": modal_config.get("ephemeral", True),
            "modal": {
                "title": modal_config.get("modal", {}).get("title", "Office Hours") + " (1/2)",
                "fields": fields_part1,
            },
        }
        modal1 = DynamicModalView(**config1)
        if existing_schedule:
            for child in modal1._modal.children:
                cid = getattr(child, 'custom_id', None)
                if cid and cid.endswith('_hours'):
                    day = cid[:-6]
                    times = existing_schedule.get(day, [])
                    if times:
                        child.default = ", ".join(times)
        try:
            values1, msg = await modal1.initiate_from_interaction(interaction)
        except Exception as e:
            self.logger.error(f"Error initiating first office hours modal: {e}")
            return
        if not values1:
            self.logger.info(f"Office hours edit cancelled by {interaction.user} at part 1")
            return
        self.logger.info(f"Values1 collected for {user_id}: {values1}")

        # If no second part
        if not fields_part2:
            await self._finalize_schedule(interaction, guild, user_id, values1)
            return

        self._pending_schedules[user_id] = values1

        # Define ContinueView
        class ContinueView(discord.ui.View):
            def __init__(self, outer: OfficeHoursCog, modal2: DynamicModalView, guild_ref: Guild, user_id_ref: str):
                super().__init__(timeout=120)
                self.outer = outer
                self.modal2 = modal2
                self.guild_ref = guild_ref
                self.user_id_ref = user_id_ref

            @discord.ui.button(label="Continue to Saturday/Sunday", style=discord.ButtonStyle.primary)
            async def continue_callback(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                existing = None
                if self.guild_ref.office_hours:
                    existing = next((oh for oh in self.guild_ref.office_hours if oh.name == self.user_id_ref), None)
                if existing:
                    for child in self.modal2._modal.children:
                        cid = getattr(child, 'custom_id', None)
                        if cid and cid.endswith('_hours'):
                            day = cid[:-6]
                            times = existing.schedule.get(day, [])
                            if times:
                                child.default = ", ".join(times)
                try:
                    values2, _ = await self.modal2.initiate_from_interaction(button_interaction)
                except Exception as e:
                    self.outer.logger.error(f"Error initiating second office hours modal: {e}")
                    await button_interaction.response.send_message("Error collecting Saturday/Sunday.", ephemeral=True)
                    return
                if not values2:
                    self.outer.logger.info(f"Office hours edit cancelled by {button_interaction.user} at part 2")
                    await button_interaction.response.send_message("Office hours update cancelled.", ephemeral=True)
                    self.outer._pending_schedules.pop(self.user_id_ref, None)
                    return
                interim = self.outer._pending_schedules.pop(self.user_id_ref, {})
                combined = {**interim, **values2}
                self.outer.logger.info(f"Values2 collected for {self.user_id_ref}: {values2}")
                await self.outer._finalize_schedule(button_interaction, self.guild_ref, self.user_id_ref, combined)
                button.disabled = True
                self.stop()
                # Edit to disable button
                try:
                    await button_interaction.edit_original_response(view=self)
                except:
                    pass

        config2 = {
            "ephemeral": modal_config.get("ephemeral", True),
            "modal": {
                "title": modal_config.get("modal", {}).get("title", "Office Hours") + " (2/2)",
                "fields": fields_part2,
            },
        }
        modal2 = DynamicModalView(**config2)

        try:
            await interaction.followup.send(
                content="First part received. Click below to continue to Saturday/Sunday:",
                ephemeral=True,
                view=ContinueView(self, modal2, guild, user_id),
            )
        except Exception:
            await interaction.response.send_message(
                content="First part received. Click below to continue to Saturday/Sunday:",
                ephemeral=True,
                view=ContinueView(self, modal2, guild, user_id),
            )

    async def _finalize_schedule(self, interaction: discord.Interaction, guild: Guild, user_id: str, collected_values: Dict[str, str]):
        schedule: Dict[str, List[str]] = {}
        for field_id, text in collected_values.items():
            if not field_id.endswith('_hours'):
                continue
            day = field_id[:-6].lower()
            if text:
                parts = [part.strip() for part in text.split(',') if part.strip()]
                schedule[day] = parts
            else:
                schedule[day] = []
        for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
            schedule.setdefault(day, [])
        self.logger.info(f"Final schedule for {user_id}: {schedule}")
        if guild.office_hours:
            guild.office_hours = [oh for oh in guild.office_hours if oh.name != user_id]
        guild.office_hours.append(OfficeHours(name=user_id, schedule=schedule))
        Database.update_document(guild, {"office_hours": guild.office_hours})
        embed = self.generate_office_hours_embed(interaction.user, schedule)
        try:
            await interaction.followup.send(
                content="Office hours schedule set!", embed=embed, ephemeral=True
            )
        except Exception:
            await interaction.response.send_message(
                content="Office hours schedule set!", embed=embed, ephemeral=True
            )

    async def _handle_clear(self, interaction: discord.Interaction, guild: Guild):
        user_id = str(interaction.user.id)
        if guild.office_hours:
            guild.office_hours = [oh for oh in guild.office_hours if oh.name != user_id]
            Database.update_document(guild, {"office_hours": guild.office_hours})
            await interaction.response.send_message(
                f"Cleared your office hours", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "You don't have any office hours set", ephemeral=True
            )

    async def _handle_display(
        self,
        interaction: discord.Interaction,
        guild: Guild,
        user: discord.User,
        is_announcement: bool = False,
    ):
        if not guild.office_hours:
            await interaction.response.send_message(
                "No office hours schedules found", ephemeral=True
            )
            return

        if is_announcement:
            embed = self.generate_weekly_schedule_embed(guild.office_hours)
            await interaction.response.send_message(embed=embed, ephemeral=False)
            return

        user_id = str(user.id)
        schedule_entry = next(
            (oh for oh in guild.office_hours if oh.name == user_id),
            None,
        )

        if not schedule_entry:
            msg = (
                "You don't have any office hours set"
                if user == interaction.user
                else f"{user.display_name} doesn't have any office hours set"
            )
            await interaction.response.send_message(msg, ephemeral=True)
            return

        embed = self.generate_office_hours_embed(user, schedule_entry.schedule)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    def generate_office_hours_embed(
        self, user: discord.User, schedule: Dict[str, List[str]]
    ) -> discord.Embed:
        embed = discord.Embed(
            title=f"Office Hours - {user.display_name}", color=colors.STATUS_SUCCESS
        )

        for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]:
            times = schedule.get(day.lower(), [])
            if times:
                embed.add_field(name=day, value="\n".join(times), inline=True)
            else:
                embed.add_field(name=day, value="No office hours", inline=True)

        return embed

    def generate_weekly_schedule_embed(
        self, schedules: List[OfficeHours]
    ) -> discord.Embed:
        """Generate a combined weekly schedule showing all office hours."""
        embed = discord.Embed(
            title="Weekly Office Hours Schedule", color=colors.STATUS_SUCCESS
        )

        days = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]

        for day in days:
            daily_schedule = []
            for oh in schedules:
                times = oh.schedule.get(day.lower(), [])
                if times:
                    try:
                        member = self.bot.get_user(int(oh.name))
                        name = member.display_name if member else f"User{oh.name}"
                    except (ValueError, AttributeError):
                        name = f"User{oh.name}"
                    times_str = ", ".join(times)
                    daily_schedule.append(f"• **{name}**: {times_str}")

            value = "\n".join(daily_schedule) if daily_schedule else "No office hours"
            embed.add_field(name=day, value=value, inline=False)

        return embed


async def setup(bot: commands.Bot):
    await bot.add_cog(OfficeHoursCog(bot))
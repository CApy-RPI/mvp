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
from backend.db.documents.guild import Guild
from backend.db.documents.guild import OfficeHours as GOfficeHours
from backend.db.database import Database
from config import settings
from frontend import config_colors as colors
from frontend.cogs.features.office_hours_config import PROFILE_CONFIG
from backend.db.documents.user import User, OfficeHours

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
        if action == "edit":
            await self._handle_edit(interaction)
        elif action == "clear":
            await self._handle_clear(interaction)
        elif action in ["show", "announce"]:
            await self._handle_display(
                interaction, user or interaction.user, is_announcement=(action == "announce")
            )

    async def _handle_edit(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)

        # 1) Load existing schedule from User (if they have one)
        existing: Dict[str, List[str]] = {}
        user_doc = Database.get_document(User, int(user_id))
        if user_doc and user_doc.office_hours:
            for d in ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]:
                existing[d] = list(getattr(user_doc.office_hours, d))

        # 2) Prepare modal field halves
        modal_cfg = PROFILE_CONFIG["office_hour_modal"]["modal"]
        fields = modal_cfg["fields"]
        part1, part2 = fields[:5], fields[5:]

        # 3) Show first modal (Mon–Fri)
        m1 = DynamicModalView(
            ephemeral=True,
            modal={
                "title": modal_cfg["title"] + " (1/2)",
                "fields": part1,
            },
        )
        # Prefill if we have existing values
        if existing:
            for item in m1._modal.children:
                cid = getattr(item, "custom_id", "")
                day = cid[:-6]
                if day in existing and existing[day]:
                    item.default = ", ".join(existing[day])

        vals1, _ = await m1.initiate_from_interaction(interaction)
        if not vals1:
            return  # user cancelled

        # 4) If no Saturday/Sunday fields, finish now
        if not part2:
            await self._finish(interaction, user_id, vals1)
            return

        # 5) Otherwise, set up second modal behind a Continue button
        m2 = DynamicModalView(
            ephemeral=True,
            modal={
                "title": modal_cfg["title"] + " (2/2)",
                "fields": part2,
            },
        )

        class ContinueView(discord.ui.View):
            def __init__(self, interim: Dict[str,str], outer: OfficeHoursCog):
                super().__init__(timeout=120)
                self.interim = interim
                self.outer = outer

            @discord.ui.button(label="Continue to Saturday/Sunday", style=discord.ButtonStyle.primary)
            async def cont(self, button_inter: discord.Interaction, btn: discord.ui.Button):
                vals2, _ = await m2.initiate_from_interaction(button_inter)
                if not vals2:
                    return  # cancelled
                combined = {**self.interim, **vals2}
                await self.outer._finish(button_inter, user_id, combined)
                btn.disabled = True
                self.stop()
                try:
                    await button_inter.edit_original_response(view=self)
                except:
                    pass

        view = ContinueView(vals1, self)
        await interaction.followup.send(
            "Your Mon–Fri hours are saved! Click below to enter Sat & Sun:",
            ephemeral=True,
            view=view,
        )
        
    async def _finish(self, interaction: discord.Interaction, user_id: str, vals: Dict[str, str]):
        # Parse the raw modal values into a schedule dict
        schedule: Dict[str, List[str]] = {}
        for cid, txt in vals.items():
            if not cid.endswith("_hours"):
                continue
            day = cid[:-6].lower()
            schedule[day] = [p.strip() for p in txt.split(",") if p.strip()]
        for d in ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]:
            schedule.setdefault(d, [])

        # Persist to the User.office_hours embedded document
        user_doc = Database.get_document(User, int(user_id))
        if not user_doc:
            await interaction.response.send_message(
                "You need to create a profile first with `/profile create`.",
                ephemeral=True,
            )
            return

        user_doc.office_hours = OfficeHours(**schedule)
        Database.update_document(user_doc, {"office_hours": user_doc.office_hours})

        # Update the Guild document to include this user's office hours
        guild_doc = Database.get_document(Guild, interaction.guild_id)
        if guild_doc is None:
            # Create guild entry if missing
            guild_doc = Guild(pk=interaction.guild_id, office_hours=[])
            Database.add_document(guild_doc)

        # Remove any existing entry for this user
        guild_doc.office_hours = [oh for oh in guild_doc.office_hours if oh.name != user_id]
        # Add new office hours entry
        new_oh = GOfficeHours(name=user_id, schedule=schedule)
        guild_doc.office_hours.append(new_oh)
        Database.update_document(guild_doc, {"office_hours": guild_doc.office_hours})

        # Send confirmation embed
        embed = self.generate_office_hours_embed(interaction.user, schedule)
        try:
            await interaction.followup.send("Office hours set!", embed=embed, ephemeral=True)
        except:
            await interaction.response.send_message("Office hours set!", embed=embed, ephemeral=True)

    async def _handle_clear(self, interaction: discord.Interaction, guild: Guild):
        user_id = str(interaction.user.id)
        guild = Database.get_document(Guild, interaction.guild_id)
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
        user: discord.User,
        is_announcement: bool = False,
    ):
        user_doc = Database.get_document(User, user.id)
        if not user_doc or not getattr(user_doc, 'office_hours', None):
            msg = "You don't have any office hours set"
            await interaction.response.send_message(msg, ephemeral=True)
            return
        oh = user_doc.office_hours
        schedule = {day: list(getattr(oh, day)) for day in [
            "monday","tuesday","wednesday","thursday","friday","saturday","sunday"
        ]}
        embed = self.generate_office_hours_embed(user, schedule)
        await interaction.response.send_message(embed=embed, ephemeral=not is_announcement)

    def generate_office_hours_embed(
        self, user: discord.User, schedule: Dict[str, List[str]]
    ) -> discord.Embed:
        embed = discord.Embed(
            title=f"Office Hours - {user.display_name}", color=colors.STATUS_SUCCESS
        )
        for day in ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]:
            times = schedule.get(day.lower(), [])
            embed.add_field(name=day, value="\n".join(times) if times else "No office hours", inline=True)
        return embed

    def generate_weekly_schedule_embed(
        self, schedules: List[GOfficeHours]
    ) -> discord.Embed:
        embed = discord.Embed(
            title="Weekly Office Hours Schedule", color=colors.STATUS_SUCCESS
        )
        days = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
        for day in days:
            daily = []
            for oh in schedules:
                times = oh.schedule.get(day.lower(), [])
                if times:
                    try:
                        member = self.bot.get_user(int(oh.name))
                        name = member.display_name if member else f"User{oh.name}"
                    except:
                        name = f"User{oh.name}"
                    daily.append(f"• **{name}**: {', '.join(times)}")
            embed.add_field(name=day, value="\n".join(daily) if daily else "No office hours", inline=False)
        return embed


async def setup(bot: commands.Bot):
    await bot.add_cog(OfficeHoursCog(bot))
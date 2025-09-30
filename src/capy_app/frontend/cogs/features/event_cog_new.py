import logging
import re
from datetime import datetime, UTC
from typing import Any
from zoneinfo import ZoneInfo

import discord

from backend.db.database import Database
from backend.db.documents.event import Event, EventDetails, EventReactions
from discord import app_commands
from discord.ext import commands

from backend.db.documents.guild import Guild
from frontend.interactions.bases.dropdown_base import DynamicDropdownView
from frontend.interactions.bases.modal_base import DynamicModalView

from config import settings

from .event_config import EVENT_CONFIG

### CONSTANTS

DEFER_LIST = ["list", "show", "announce", "myevents"]
EPHEMERAL_LIST = ["list", "show", "delete", "announce", "myevents"]

REQUIRED_FIELDS = [
    "event_name",
    "event_date",
    "event_time",
    "event_location",
    "event_description",
]

# TODO: Expand pattern such that it validates date >= 01/01/2024 & day exists (month variation and leap year)
DATE_PATTERN = re.compile(r"^((0[1-9]|1[0-2])/(0[1-9]|[1-2][0-9]|3[0-1])/(\d{2}))$")
TIME_PATTERN = re.compile(
    r"^((0[1-9]|1[0-2]):([0-5][0-9])\s+(AM|PM))$"
)  # Note: the original had /s+[A-Z]{2,4} tacked onto the end, and I don't know why.

DATETIME_PATTERN = "%m/%d/%Y %I:%M %p"

###


def parse_datetime(date: str, time: str, timezone: str) -> datetime:
    """Parse time, date, and timezone into a datetime object"""
    dt = datetime.strptime(f"{date} {time}", DATETIME_PATTERN)
    dt.replace(tzinfo=ZoneInfo(timezone))
    return dt

def now() -> datetime:
    """Return the current time in UTC"""
    return datetime.now(UTC)





class EventCogNew(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.config = EVENT_CONFIG
        self.logger = logging.getLogger(f"discord.cog.{self.__class__.__name__.lower()}")

        def _get_default_timezone() -> str:
            """Helper to get default timezone from config dropdowns."""
            fallback_dropdowns: list[dict[str, Any]] = self.config["timezone_dropdown"].get("dropdowns", [])
            for dropdown in fallback_dropdowns:
                options = dropdown.get("options", [])
                for option in options:
                    if "default" in option:
                        value = option.get("value")
                        if isinstance(value, str) and value:
                            return value
            return "US/Eastern"

        self.default_timezone = _get_default_timezone()

    # Register the /event command for the debug guild only
    @app_commands.guilds(discord.Object(id=settings.DEBUG_GUILD_ID if settings.DEBUG_GUILD_ID is not None else 0))
    @app_commands.command(name="event", description="Manage events")
    @app_commands.describe(action="The action to perform with events")
    @app_commands.choices(
        action=[
            app_commands.Choice(name="create", value="create"),
            app_commands.Choice(name="list", value="list"),
            app_commands.Choice(name="show", value="show"),
            app_commands.Choice(name="edit", value="edit"),
            app_commands.Choice(name="delete", value="delete"),
            app_commands.Choice(name="announce", value="announce"),
            app_commands.Choice(name="myevents", value="myevents"),
        ]
    )
    async def event(self, interaction: discord.Interaction, action: str) -> None:
        should_defer = action in DEFER_LIST
        is_ephemeral = action in EPHEMERAL_LIST

        if should_defer:
            await interaction.response.defer(ephemeral=is_ephemeral)

        match action:
            case "create":
                await self._create_event(interaction)
            case "delete":
                await self._delete_event(interaction)
            case "edit":
                await self._edit_event(interaction)
            case "list":
                await self._list_guild_events(interaction)
            case "show":
                await self._show_event(interaction)
            case "myevents":
                await self._show_user_events(interaction)
            case "announce":
                await self._announce_event(interaction)

    async def _create_event(self, interaction: discord.Interaction) -> None:
        """Handle event creation"""

        self.logger.info(f"Event creation requested by {interaction.user}")

        # Get event data from modal
        self.logger.info("Creating modal view")
        modal_view = DynamicModalView(**self.config["event_modal"])
        self.logger.info("Initiating modal interaction")
        event_data, modal_message = await modal_view.initiate_from_interaction(interaction)

        self.logger.info(f"Modal result: data={event_data is not None},message exists={modal_message is not None}")

        # Ensure event data exists
        if not event_data:
            raise ValueError("No event data received")

        # TODO We don't know what this fixes
        # # If the modal returns a None message, it has crashed
        # if not modal_message:
        #     self.logger.error("Modal message not received")
        #     modal_message = await interaction.followup.send(
        #         "ERR: Modal has failed to display. **Event creation is still ongoing**.", ephemeral=True, wait=True
        #     )

        # Validate the event data
        self.logger.info("Validating event data")
        if not self._validate_event_form(event_data):
            self.logger.info("Invalid form data inputted")
            await modal_message.edit(
                content="Invalid event data. Please check date/time formats and try again.",
                view=None,
            )
            return

        # Get selected timezone
        timezone, dropdown_message = await self._get_timezone_selection(modal_message)

        # Parse the date and time into a datetime object
        event_time = parse_datetime(event_data["event_date"], event_data["event_time"], timezone)

        # Create and save the event
        new_event, event_id = await self._save_new_event(interaction, event_data, event_time)

        # Show event details to user
        await self._show_event_embed(message=dropdown_message, event=new_event)
        self.logger.info(f"Event '{event_data['event_name']}' created with ID {event_id}")

    def _validate_event_form(self, form_data: dict[str, str]) -> bool:
        """Validates that the data contained in an event form contains required fields and matches conventions"""

        # Ensure form_data contains all required fields
        for field in REQUIRED_FIELDS:
            if field not in form_data:
                self.logger.info(f"Field '{field}' not found in form data")
                return False

        # Ensure date format matches US standard (MM/DD/YY)
        date_str = form_data["event_date"]
        if not re.match(DATE_PATTERN, date_str):
            self.logger.info(f"Date '{date_str}' does not match MM/DD/YY format")
            return False

        # Ensure time format matches standard (HH:MM AM|PM)
        time_str = form_data["event_time"]
        if not re.match(TIME_PATTERN, time_str, re.IGNORECASE):
            self.logger.info(f"Time '{time_str}' does not match HH:MM AM|PM format")
            return False

        return True

    async def _get_timezone_selection(self, modal_message) -> tuple[str, Any]:
        """ "Creates timezone selection dropdown menu"""
        self.logger.info("Creating timezone dropdown")
        timezone_config = self.config["timezone_dropdown"].copy()
        timezone_config.pop("placeholder", None)

        # Format dropdown selections
        dropdowns: list[dict[str, Any]] = timezone_config.get("dropdowns", [])
        for dropdown in dropdowns:
            if "options" in dropdown:
                dropdown["selections"] = dropdown.pop("options")
        timezone_config["dropdowns"] = dropdowns

        # Create view
        timezone_view = DynamicDropdownView(**timezone_config)
        timezone_data, dropdown_message = await timezone_view.initiate_from_message(
            modal_message, "Please select a timezone for the event:"
        )

        # If no timezone selection is returned, use helper to get default
        if not timezone_data:
            self.logger.info("Timezone data not received, falling back to default")
            timezone_data = {"timezone_selection": [self.default_timezone]}

        if not timezone_data["timezone_selection"]:
            self.logger.info("No timezone selection present, falling back to default")
            timezone_data["timezone_selection"] = self.default_timezone

        timezone = timezone_data["timezone_selection"][0]
        return timezone, dropdown_message

    async def _save_new_event(self, interaction, event_data, event_time: datetime) -> tuple[Event, int]:
        """Creates and saves a new event to the database & guild(s)"""
        event_id = int(datetime.now(event_time.tzinfo).timestamp() * 1000)
        new_event = Event(
            _id=event_id,
            guild_id=interaction.guild_id,
            yes_users=[],
            maybe_users=[],
            no_users=[],
            message_id=0, # TODO is this right? Should we get from the interaction?
            details=EventDetails(
                name=event_data["event_name"],
                description=event_data["event_description"],
                time=event_time,
                location=event_data["event_location"],
                reactions=EventReactions(yes=0, no=0, maybe=0),
            ),
        )
        Database.add_document(new_event)
        self.logger.info(f"Event saved to database with ID {event_id}")

        guild = Database.get_document(Guild, interaction.guild_id)
        if not guild:
            guild = Guild(_id=interaction.guild_id, events=[])
            Database.add_document(guild)
        elif not hasattr(guild, "events"):
            guild.events = []
        guild.events.append(event_id)
        Database.update_document(guild, {"events": guild.events})
        self.logger.info(f"Guild document updated with event ID {event_id}")
        return new_event, event_id

    async def _show_event_embed(self, event: Event, message: discord.Message | None = None, interaction: discord.Interaction | None = None) -> None:
        """Display event details in an embed"""
        # Determine if the event is old (in the past)
        current_time = now()
        event_time = event.details.time
        if event_time.tzinfo is None:
            event_time = event_time.replace(tzinfo=UTC)
        is_old = event_time < current_time

        # Create the embed, tinting red for old events
        title_prefix = "[OLD] " if is_old else ""
        embed = discord.Embed(
            title=f"{title_prefix}{event.details.name}",
            description=event.details.description,
            color=discord.Color.red() if is_old else discord.Color.purple(),
        )

        # Add event details
        localized_time = self._format_datetime(event.details.time)
        embed.add_field(name="Date/Time", value=localized_time, inline=True)
        embed.add_field(name="Location", value=event.details.location, inline=True)
        embed.add_field(name="Status", value=("OLD" if is_old else "UPCOMING"), inline=True)

        # Add attendance count
        total_attendees = len(event.yes_users)
        embed.add_field(name="Attendees", value=str(total_attendees), inline=True)

        # Add RSVP breakdown if present
        if hasattr(event.details, "reactions"):
            reactions_text = (
                f"✅ Yes: {event.details.reactions.yes} | "
                f"❌ No: {event.details.reactions.no} | "
                f"❔ Maybe: {event.details.reactions.maybe}"
            )
            embed.add_field(name="RSVPs", value=reactions_text, inline=False)

        # Footer with event ID
        embed.set_footer(text=f"Event ID: {event._id}")

        if message:
            await message.edit(content=None, embed=embed, view=None)
        elif interaction:
            await interaction.followup.send(embed=embed, ephemeral=True)

    def _format_datetime(self, dt: datetime, timezone_str: str = "US/Eastern") -> str:
        """Format a datetime object for display with timezone."""
        try:
            # Ensure datetime has timezone
            if dt.tzinfo is None:
                dt.replace(tzinfo=UTC)

            # Convert to desired timezone
            target_tz = ZoneInfo(timezone_str)
            localized_dt = dt.astimezone(target_tz)

            # Format for display
            return localized_dt.strftime("%Y-%m-%d %I:%M %p %Z")
        except Exception as e:
            self.logger.error(f"Error formatting datetime: {e}")
            return str(dt)

    async def _delete_event(self, interaction: discord.Interaction) -> None:
        """Handle event deletion"""

    async def _edit_event(self, interaction: discord.Interaction) -> None:
        """Handle event editing"""

    async def _list_guild_events(self, interaction: discord.Interaction) -> None:
        """List events attributed to a guild"""

    async def _show_event(self, interaction: discord.Interaction) -> None:
        """Show details of an event"""

    async def _show_user_events(self, interaction: discord.Interaction) -> None:
        """Show events subscribed to by a user"""

    async def _announce_event(self, interaction: discord.Interaction) -> None:
        """Announce an event"""

import logging
import re
from datetime import datetime, UTC
from enum import Enum, StrEnum, auto
from optparse import Option
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

EVENT_SELECTIONS = ("event_selection_upcoming","event_selection_old","event_selection")

###

class Action(StrEnum):
    DELETE = auto()
    VIEW = auto()
    EDIT = auto()

def parse_datetime(date: str, time: str, timezone: str) -> datetime:
    """Parse time, date, and timezone into a datetime object"""
    dt = datetime.strptime(f"{date} {time}", DATETIME_PATTERN)
    dt.replace(tzinfo=ZoneInfo(timezone))
    return dt

def now() -> datetime:
    """Return the current time in UTC"""
    return datetime.now(UTC)

def _event_time(ev: Event): # This is marked private so not to conflict with any variables event_time
    t = ev.details.time
    return t.replace(tzinfo=UTC) if t.tzinfo is None else t


def get_guild_events_for_action(guild_id: int, action: Action) -> list[Event | None]:
    """Gets the events for a guild that match a given action"""
    # Fetch guild from DB
    guild = Database.get_document(Guild, guild_id)
    if not guild or not hasattr(guild, "events") or not guild.events:
        # If no events found, return empty list
        return []
    current_time = now()
    events: list[Event] = []
    for event_id in getattr(guild, "events", []):
        event = Database.get_document(Event, event_id)
        if event and hasattr(event, "details"):
            event_time = event.details.time
            # If event time is naive, localize to UTC
            if event_time.tzinfo is None:
                event_time = event_time.replace(tzinfo=UTC)
            # For delete, view, and edit include all events; otherwise, only future events
            if action in (Action.DELETE, Action.EDIT, Action.VIEW) or event_time >= current_time:
                events.append(event)
    return events


def get_event_error_msg(guild_id: int) -> str:
    """Returns appropriate error message for event selection"""
    guild = Database.get_document(Guild, guild_id)
    if not guild or not hasattr(guild, "events") or not guild.events:
        return "No events found for this server."
    return "No matching events found."


def build_event_dropdown_config(options, action: Action):
    """Build dropdown configuration for event selection view"""
    dropdowns = []
    if isinstance(options, dict):
        upcoming = options.get("upcoming", [])
        old = options.get("old", [])
        if upcoming:
            dropdowns.append(
                {
                    "custom_id": "event_selection_upcoming",
                    "placeholder": f"Select an Upcoming event to {action}",
                    "min_values": 1,
                    "max_values": 1,
                    "selections": upcoming,
                }
            )
        if old:
            dropdowns.append(
                {
                    "custom_id": "event_selection_old",
                    "placeholder": f"Select an Old event to {action}",
                    "min_values": 1,
                    "max_values": 1,
                    "selections": old,
                }
            )
    else:
        dropdowns.append(
            {
                "custom_id": "event_selection",
                "placeholder": f"Select an event to {action}",
                "min_values": 1,
                "max_values": 1,
                "selections": options,
            }
        )
    return {
        "ephemeral": True,
        "buttons": (True, True),
        "timeout": 180,
        "dropdowns": dropdowns,
    }


class EventCogNew(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.config = EVENT_CONFIG
        self.logger = logging.getLogger(f"discord.cog.{self.__class__.__name__.lower()}")

        def _get_default_timezone() -> str:
            """Helper to get default timezone from config dropdowns."""
            fallback_dropdowns = self.config["timezone_dropdown"].get("dropdowns", [])
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
        timezone_config:dict[str, Any] = self.config["timezone_dropdown"].copy()
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
        # Retrieve guild from DB
        guild = Database.get_document(Guild, interaction.guild_id)

        # Check if guild has events to delete
        if not guild or not hasattr(guild, "events") or not guild.events:
            await interaction.response.send_message(
                "No events found for this server.", ephemeral=True
            )
            return

        # Check any events have matching details
        has_events = any(
            Database.get_document(Event, event_id)
            and hasattr(Database.get_document(Event, event_id), "details")
            for event_id in guild.events
        )

        if not has_events:
            await interaction.response.send_message(
                "No events found for this server.", ephemeral=True
            )
            return

        # Deletion process
        event, message = await self._get_event_selection(interaction, Action.DELETE)
        if not event or not message:
            # If no event or message is returned, exit early
            return

        # Get confirmation from user
        confirmed = await self._show_delete_confirmation(message, event)

        if confirmed is None:
            # If confirmation times out, notify user
            await self._edit_message_safe(message, "Event deletion timed out.")
            return

        if confirmed:
            # If user confirms deletion, attempt to delete event
            delete_error = await self._delete_event_and_cleanup(event, interaction.guild_id)
            if delete_error:
                # If error occurs during deletion, notify user
                await self._edit_message_safe(
                    message, f"Error deleting event '{event.details.name}': {delete_error}"
                )
            else:
                # Notify user of successful deletion
                await self._edit_message_safe(
                    message, f"Event '{event.details.name}' has been deleted."
                )
        else:
            # If user cancels deletion, notify user
            await self._edit_message_safe(message, "Event deletion cancelled.")


    async def _get_event_selection(self, interaction: discord.Interaction, action: Action) -> tuple[Event | None, discord.Message | None]:
        """Gets event selection from dropdown"""
        selected_event = None
        message = None
        error_msg = None

        # Get all applicable events for the given action
        try:
            if not interaction.guild_id:
                raise ValueError("Guild ID not provided")

            guild_events = get_guild_events_for_action(interaction.guild_id, action)
            if not guild_events:
                # If no events found, set error message
                error_msg = get_event_error_msg(interaction.guild_id)
            else:
                # Build dropdown options & config
                options = self._build_event_dropdown_options(guild_events)
                dropdown_config = build_event_dropdown_config(options, action)
                view = DynamicDropdownView(**dropdown_config)

                # Show dropdown
                values, message = await self._get_dropdown_selection(interaction, view, action)
                if not values or not message:
                    # If no selection made, set error message
                    error_msg = "No event selected."
                else:
                    # Get selected event ID
                    selected_id_str = None
                    for key in EVENT_SELECTIONS:
                        selected_list = values.get(key, [])
                        if selected_list:
                            selected_id_str = selected_list[0]
                            break
                    if not selected_id_str:
                        error_msg = "No event selected."
                    else:
                        try:
                            # Try to convert selected ID to int and fetch event from database
                            selected_id = int(selected_id_str)
                            selected_event = Database.get_document(Event, selected_id)
                            if not selected_event:
                                error_msg = f"Error: Event with ID {selected_id} not found."
                        except ValueError:
                            # If conversion fails, set error message
                            error_msg = f"Error: Invalid event ID selected ({selected_id_str})."
        except Exception as e:
            # Log unexpected errors and set generic error message
            self.logger.error(f"Error in get_event_selection: {e!s}", exc_info=True)
            error_msg = "An unexpected error occurred while selecting the event."
        if error_msg:
            # If any error occurred, send error message and return None
            await self._send_event_selection_error(
                interaction,
                error_msg,
                message,
            )
            return None, message
        # Return the selected event and message object
        return selected_event, message

    def _build_event_dropdown_options(self, events):
        """Build dropdown groups for upcoming and past events"""
        current_time = now()
        upcoming = []
        old = []

        # Sort by time
        try:
            sorted_events = sorted(events, key=lambda e: _event_time(e))
        except (ValueError, TypeError) as e:
            # If sorting failed, keep the unsorted version
            self.logger.error(f"Error sorting events: {e!s}")
            sorted_events = events

        for event in sorted_events:
            event_time = event.details.time
            if event_time.tzinfo is None:
                event_time.replace(tzinfo=UTC)
            is_old = event_time < current_time
            option = {
                "label": f"{'[OLD] ' if is_old else ''}{event.details.name}",
                "description": self._format_datetime(event.details.time)[:99],
                "value": str(event._id),
            }
            if is_old:
                old.append(option)
            else:
                upcoming.append(option)
        return {"upcoming": upcoming, "old": old}

    async def _get_dropdown_selection(self, interaction, view: DynamicDropdownView, action: Action):
        """Shows a dropdown and returns the user selection"""
        values = None
        message = None

        if interaction.response.is_done():
            # If response is already set, create & use a followup message for the dropdown
            message = await interaction.followup.send(
                f"Please select an event to {action.value}:",
                view=view,
                ephemeral=True,
                wait=True,
            )
            await view.wait()

            selections = {}

            # Collect selected values from dropdowns
            for dropdown in getattr(view, "_dropdowns", []):
                if hasattr(dropdown, "selected_values") and dropdown.selected_values:
                    selections[getattr(dropdown, "custom_id", "event_selection")] = (
                        dropdown.selected_values
                    )
            values = selections if getattr(view, "accepted", False) else None

            # If user cancelled selection, update message and return None
            if hasattr(view, "cancelled") and getattr(view, "cancelled", False):
                await message.edit(
                    content=f"Event selection for {action.value} was cancelled.",
                    view=None,
                    embed=None,
                )
                return None, message
        else:
            # If response not sent, initiate dropdown from current interaction
            values, message = await view.initiate_from_interaction(
                interaction, f"Please select an event to {action.value}:"
            )

        if not getattr(view, "accepted", False):
            if getattr(view, "_timed_out", False):
                await message.edit(content="Event selection timed out.", view=None, embed=None)
            else:
                await message.edit(content="Event selection cancelled.", view=None, embed=None)
            return None, message
        # Return selected values and message object
        return values, message

    async def _send_event_selection_error(self, interaction: discord.Interaction, error_msg: str, message: Any = None) -> None:
        return

    async def _show_delete_confirmation(self, message: discord.Message, event: Event):
        return

    async def _edit_message_safe(self, message, content):
        return

    async def _delete_event_and_cleanup(self, event, guild_id):
        return

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

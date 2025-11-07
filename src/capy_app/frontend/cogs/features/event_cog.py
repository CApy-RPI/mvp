import logging
import re
from contextlib import suppress
from datetime import UTC, datetime, tzinfo
from enum import StrEnum, auto
from typing import Any
from zoneinfo import ZoneInfo

import discord
from backend.db.database import Database
from backend.db.documents.event import Event, EventDetails, EventReactions
from backend.db.documents.guild import Guild
from backend.db.documents.user import User
from discord import app_commands
from discord.ext import commands
from frontend.interactions.bases.button_base import ConfirmDeleteView, ConfirmView, EditView
from frontend.interactions.bases.dropdown_base import DynamicDropdownView
from frontend.interactions.bases.modal_base import DynamicModalView

from config import settings

from .event_config import EVENT_CONFIG

### CONSTANTS

# TODO: Expand pattern such that it validates date >= 01/01/2024 & day exists (month variation and leap year)
# Regex pattern for MM/DD/YY
DATE_PATTERN = re.compile(r"^((0[1-9]|1[0-2])/(0[1-9]|[1-2][0-9]|3[0-1])/(\d{2}))$")
# Regex pattern for HH:MM AM | PM
TIME_PATTERN = re.compile(
    r"^((0[1-9]|1[0-2]):([0-5][0-9])\s+(AM|PM))$", re.IGNORECASE
)  # Note: the original had /s+[A-Z]{2,4} tacked onto the end, and I don't know why.

# Pattern for datetimes
# Reference: https://docs.python.org/3/library/datetime.html
DATETIME_PATTERN = "%m/%d/%y %I:%M %p"

# The allowed reactions for RSVPing
ALLOWED_REACTIONS = ["✅", "❌", "❔"]

###


class Action(StrEnum):
    """
    An action taken over events
    """

    DELETE = auto()
    VIEW = auto()
    EDIT = auto()
    ANNOUNCE = auto()


class RSVPEmoji(StrEnum):
    """
    An emoji for RSVPing
    """

    YES = "✅"
    NO = "❌"
    MAYBE = "❔"

    @staticmethod
    def reverse(emoji):
        """
        Returns the matching RSVP emoji key from an emoji
        """
        match emoji:
            case "✅":
                return RSVPEmoji.YES
            case "❌":
                return RSVPEmoji.NO
            case "❔":
                return RSVPEmoji.MAYBE
            case _:
                return None


def parse_datetime(date: str, time: str, timezone: str) -> datetime:
    """
    Parse time, date, and timezone into a datetime object
    """
    dt = datetime.strptime(f"{date} {time}", DATETIME_PATTERN)
    # TODO I don't love creating an object just to throw it away- look into a pattern with timezone included
    dt = localize(dt, ZoneInfo(timezone))
    return dt


def now() -> datetime:
    """
    Return the current time in UTC
    """
    return datetime.now(UTC)


def _event_time(ev: Event):  # This is marked private so not to conflict with any variables event_time
    """
    Return the time of an event, using UTC if it's timezone-naive
    """
    t = ev.details.time
    return localize(t) if t.tzinfo is None else t


def get_guild_events_for_action(guild_id: int, action: Action) -> list[Event | None]:
    """
    Gets the events for a guild that match a given action
    """
    # Fetch guild from DB
    guild = Database.get_document(Guild, guild_id)
    if not guild or not hasattr(guild, "events") or not guild.events:
        # If no events found, return empty list
        return []
    current_time = now()
    events: list[Event] = []
    # Collect the events for the specified action
    for event_id in getattr(guild, "events", []):
        event = Database.get_document(Event, event_id)
        if event and hasattr(event, "details"):
            event_time = event.details.time
            # If event time is naive, localize to UTC
            if event_time.tzinfo is None:
                event_time = localize(event_time)
            # For delete, view, and edit include all events; otherwise, only future events
            if action in (Action.DELETE, Action.EDIT, Action.VIEW) or event_time >= current_time:
                events.append(event)
    return events


def get_event_error_msg(guild_id: int) -> str:
    """
    Returns appropriate error message for event selection
    """
    guild = Database.get_document(Guild, guild_id)
    if not guild or not hasattr(guild, "events") or not guild.events:
        return "No events found for this server."
    return "No matching events found."


def build_event_dropdown_config(options, action: Action):
    """
    Build dropdown configuration for event selection view
    """
    dropdowns = []
    if isinstance(options, dict):
        upcoming = options.get("upcoming", [])
        old = options.get("old", [])
        # Add the upcoming events dropdown
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
            # Add the old events dropdown
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
        # If options isn't a dict, the only needed dropdown contains all events
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


async def send_event_selection_error(interaction, error_msg, message=None):
    """
    Helper for consolidating and sending error messages occurring in event selection
    """
    if message:
        # If a message object is provided, try to edit it with the error message
        with suppress(discord.NotFound, discord.HTTPException):
            await message.edit(
                content=error_msg,
                view=None,
                embed=None,
            )
    else:
        try:
            if interaction.response.is_done():
                # If the interaction response is already sent, use followup
                await interaction.followup.send(error_msg, ephemeral=True)
            else:
                # Otherwise, send the error as the initial response
                await interaction.response.send_message(error_msg, ephemeral=True)
        except (discord.NotFound, discord.HTTPException):
            # Suppress common exceptions if message cannot be sent
            pass


async def get_dropdown_selection(interaction, view: DynamicDropdownView, action: Action):
    """
    Shows a dropdown and returns the user selection
    """
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
                selections[getattr(dropdown, "custom_id", "event_selection")] = dropdown.selected_values
        values = selections if getattr(view, "accepted", False) else None

        # If user cancelled selection, update message and return None
        if hasattr(view, "accepted") and not getattr(view, "accepted", False):
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

    # Handle timeouts and cancellations
    if not getattr(view, "accepted", False):
        if getattr(view, "_timed_out", False):
            await message.edit(content="Event selection timed out.", view=None, embed=None)
        else:
            await message.edit(content="Event selection cancelled.", view=None, embed=None)
        return None, message
    # Return selected values and message object
    return values, message


async def edit_message_safe(message, content):
    """
    Safely edit a message, suppressing common exceptions.
    """
    with suppress(discord.NotFound, discord.HTTPException):
        await message.edit(content=content, view=None, embed=None)


def localize(dt: datetime, tz: tzinfo = UTC) -> datetime:
    """
    Localizes a datetime object to have a given timezone, defaulting to UTC.
    """
    return dt.replace(tzinfo=tz)


async def fetch_message_if_possible(channel, message_id):
    """
    Fetches a message, if possible
    """
    if isinstance(channel, (discord.TextChannel | discord.Thread)):
        with suppress(discord.NotFound, discord.Forbidden):
            return await channel.fetch_message(message_id)
    return None


async def remove_other_reactions(message, emoji, user):
    """
    Removes all reactions other than a given reaction attributed to a given user
    """
    for reaction in message.reactions:
        if str(reaction.emoji) != emoji and user:
            with suppress(discord.NotFound, discord.HTTPException):
                await reaction.remove(user)


def verify_interaction(interaction):
    """
    Ensures a given interaction has valid fields.
    """
    if not interaction.guild_id:
        raise ValueError("No guild id provided")


def verify_guild_events(guild):
    """
    Ensures a guild has some events.
    """
    return guild and hasattr(guild, "events") and guild.events


def verify_user_events(user):
    """
    Ensures a user has some events.
    """
    return user and hasattr(user, "events") and user.events


def verify_field(o, field):
    """
    Ensures an object exists and has a field
    """
    return o and hasattr(o, field)


def add_reactions(message, reactions):
    """
    Adds some reactions to a message
    """
    for reaction in reactions:
        message.add_reaction(reaction)


def build_removals(emoji):
    """
    Builds a set of RSVPEmoji to remove as reactions from a message
    """
    remove: set[RSVPEmoji] = set()

    if emoji in {"✅", "❔"}:
        remove.add(RSVPEmoji.NO)
    if emoji in {"✅", "❌"}:
        remove.add(RSVPEmoji.MAYBE)
    if emoji in {"❔", "❌"}:
        remove.add(RSVPEmoji.YES)

    return remove


async def display_content(message, button_interaction, content):
    """
    Displays content to either a message or a button interaction, depending on which exists
    """
    if message:
        await message.edit(content=content, view=None)
    else:
        await button_interaction.followup.send(content, ephemeral=True)


def selected_tz(timezone_data, current_tz):
    """
    Returns the selected timezone field in a dict, falling back to the current timezone.
    """
    if timezone_data and timezone_data.get("timezone_selection"):
        return timezone_data.get("timezone_selection", [current_tz])[0]
    else:
        return current_tz


def all_false(*elems):
    """
    Returns if all passed in are false
    """
    return all(not elem for elem in elems)


def all_true(*elems):
    """
    Returns if all passed in are true
    """
    return all(elem for elem in elems)


def get_announcement_channel(channel_id, interaction):
    """
    Checks if a passed in channel is the guild's announcement channel, falling back to the channel named "announcements"
    """
    announcement_channel = None
    if channel_id:
        chan = interaction.guild.get_channel(channel_id)
        if isinstance(chan, discord.TextChannel):
            announcement_channel = chan
    if announcement_channel is None:
        # Fallback by name for legacy behavior
        announcement_channel = discord.utils.get(interaction.guild.text_channels, name="announcements")

    return announcement_channel


class EventCog(commands.Cog):
    """
    Cog for handling actions relating to events
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.config = EVENT_CONFIG
        self.logger = logging.getLogger(f"discord.cog.{self.__class__.__name__.lower()}")

        def _get_default_timezone() -> str:
            """
            Helper to get default timezone from config dropdowns.
            """
            fallback_dropdowns = self.config["timezone_dropdown"].get("dropdowns", [])
            for dropdown in fallback_dropdowns:
                options = dropdown.get("options", [])
                for option in options:
                    if "default" in option:
                        value = option.get("value")
                        if isinstance(value, str) and value:
                            return value
            return "US/Eastern"  # Fall back to US/Eastern

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
        """
        Handler for the /event command
        """
        # Check if the action needs to defer and/or be ephemeral
        should_defer = action in ["list", "show", "announce", "myevents"]
        is_ephemeral = action in ["list", "show", "delete", "announce", "myevents"]

        if should_defer:
            await interaction.response.defer(ephemeral=is_ephemeral)

        # Use the correct handler for the action
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
        """
        Handle event creation
        """

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
        """
        Validates that the data contained in an event form contains required fields and matches conventions
        """

        # Ensure form_data contains all required fields
        for field in [
            "event_name",
            "event_date",
            "event_time",
            "event_location",
            "event_description",
        ]:
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
        if not re.match(TIME_PATTERN, time_str):
            self.logger.info(f"Time '{time_str}' does not match HH:MM AM|PM format")
            return False

        return True

    async def _get_timezone_selection(self, modal_message) -> tuple[str, Any]:
        """
        Creates timezone selection dropdown menu
        """
        self.logger.info("Creating timezone dropdown")
        timezone_config: dict[str, Any] = self.config["timezone_dropdown"].copy()
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
        """
        Creates and saves a new event to the database & guild(s)
        """
        event_id = int(datetime.now(event_time.tzinfo).timestamp() * 1000)
        new_event = Event(
            _id=event_id,
            guild_id=interaction.guild_id,
            yes_users=[],
            maybe_users=[],
            no_users=[],
            message_id=0,  # TODO is this right? Should we get from the interaction?
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
            # If the guild has never existed in the database before, add it
            guild = Guild(_id=interaction.guild_id, events=[])
            Database.add_document(guild)
        elif not hasattr(guild, "events"):
            guild.events = []
        guild.events.append(event_id)
        Database.update_document(guild, {"events": guild.events})
        self.logger.info(f"Guild document updated with event ID {event_id}")
        return new_event, event_id

    async def _show_event_embed(
        self, event: Event, message: discord.Message | None = None, interaction: discord.Interaction | None = None
    ) -> None:
        """
        Display event details in an embed
        """
        # Determine if the event is old (in the past)
        current_time = now()
        event_time = event.details.time
        if event_time.tzinfo is None:
            event_time = localize(event_time)
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
        """
        Format a datetime object for display with timezone.
        """
        try:
            # Ensure datetime has timezone
            if dt.tzinfo is None:
                dt = localize(dt)

            # Convert to desired timezone
            target_tz = ZoneInfo(timezone_str)
            localized_dt = dt.astimezone(target_tz)

            # Format for display
            return localized_dt.strftime("%Y-%m-%d %I:%M %p %Z")
        except Exception as e:
            self.logger.error(f"Error formatting datetime: {e}")
            return str(dt)

    async def _delete_event(self, interaction: discord.Interaction) -> None:
        """
        Handle event deletion
        """
        # Retrieve guild from DB
        guild = Database.get_document(Guild, interaction.guild_id)

        # Check if guild has events to delete
        if not verify_guild_events(guild):
            await interaction.response.send_message("No events found for this server.", ephemeral=True)
            return

        # Check any events have matching details
        has_events = any(
            Database.get_document(Event, event_id) and hasattr(Database.get_document(Event, event_id), "details")
            for event_id in guild.events
        )

        if not has_events:
            await interaction.response.send_message("No events found for this server.", ephemeral=True)
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
            await edit_message_safe(message, "Event deletion timed out.")
            return

        if confirmed:
            # If user confirms deletion, attempt to delete event
            delete_error = await self._delete_event_and_cleanup(event, interaction.guild_id)
            if delete_error:
                # If error occurs during deletion, notify user
                await edit_message_safe(message, f"Error deleting event '{event.details.name}': {delete_error}")
            else:
                # Notify user of successful deletion
                await edit_message_safe(message, f"Event '{event.details.name}' has been deleted.")
        else:
            # If user cancels deletion, notify user
            await edit_message_safe(message, "Event deletion cancelled.")

    async def _get_event_selection(
        self, interaction: discord.Interaction, action: Action
    ) -> tuple[Event | None, discord.Message | None]:
        """
        Gets event selection from dropdown
        """
        selected_event = None
        message = None
        error_msg = None

        # Get all applicable events for the given action
        try:
            verify_interaction(interaction)

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
                values, message = await get_dropdown_selection(interaction, view, action)

                # get_dropdown selection already handles editing the message on a cancellation or timeout,
                # so no need to set error msg
                if values is not None:
                    # Get selected event ID
                    selected_id_str = None
                    for key in ("event_selection_upcoming", "event_selection_old", "event_selection"):
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
            await send_event_selection_error(
                interaction,
                error_msg,
                message,
            )
            return None, message
        # Return the selected event and message object
        return selected_event, message

    def _build_event_dropdown_options(self, events):
        """
        Build dropdown groups for upcoming and past events
        """
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
                # Set event time to UTC if timezone-naive
                event_time = localize(event_time)
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

    async def _show_delete_confirmation(self, message: discord.Message, event: Event):
        """
        Show deletion confirmation to user
        """
        view = ConfirmDeleteView()
        try:
            await message.edit(
                content=f"⚠️ Are you sure you want to delete the event '{event.details.name}'?",
                view=view,
                embed=None,
            )
        except (discord.NotFound, discord.HTTPException) as e:
            # If message can't be edited, log and return None
            self.logger.warning(f"Failed to edit message for delete confirmation: {e}")
            return None

        await view.wait()
        # Return the confirmation choice (T/F/None)
        return view.value

    def _remove_event_from_user(self, user_id, event):
        """
        Removes an event from a user in the database
        """
        try:
            user = Database.get_document(User, user_id)
            if user and hasattr(user, "events") and event._id in user.events:
                user.events.remove(event._id)
                user.save()
                self.logger.info(f"Removed event {event._id} from user {user_id}'s events")
        except Exception as e:
            self.logger.error(f"Error removing event {event._id} from user {user_id}: {e}")

    async def _delete_event_and_cleanup(self, event, guild_id):
        """
        Remove event from database
        """

        # Remove from guild event list
        try:
            guild = Database.get_document(Guild, guild_id)
            if guild and hasattr(guild, "events") and event._id in guild.events:
                guild.events.remove(event._id)
                Database.update_document(guild, {"events": guild.events})
                self.logger.info(f"Removed event {event._id} from guild {guild_id}")
        except Exception as e:
            self.logger.error(f"Error removing event {event._id} from guild: {e}")

        # Remove from all users' lists
        all_users = (
            set(getattr(event, "yes_users", []))
            | set(getattr(event, "maybe_users", []))
            | set(getattr(event, "no_users", []))
        )
        for user_id in all_users:
            self._remove_event_from_user(user_id, event)

        # Remove from database
        try:
            Database.delete_document(event)
            self.logger.info(f"Event {event._id} '{event.details.name}' deleted")
            return None
        except Exception as e:
            self.logger.error(f"Error deleting event {event._id}: {e}")
            return e

    async def _edit_event(self, interaction: discord.Interaction) -> None:
        """
        Handle event editing
        """

        event, message = await self._get_event_selection(interaction, Action.EDIT)
        if not event or not message:
            # If no event or message is returned, exit early
            return

        view = EditView(
            lambda button_interaction: self._handle_edit_event_button(button_interaction, event, message),
            ephemeral=True,
        )

        await message.edit(
            content='Press "Edit" below to edit this event or press "Cancel" to cancel editing:',
            view=view,
        )
        await view.wait()

        if view.value is False:
            # If the user cancels editing, update the message accordingly
            with suppress(discord.NotFound, discord.HTTPException):
                await message.edit(
                    content="Event editing cancelled.",
                    view=None,
                    embed=None,
                )

    async def _handle_edit_event_button(self, button_interaction, event: Event, message):
        """
        Handles logic for creation of the edit event button
        """
        modal_config = await self._get_prefilled__modal_config(event)
        modal_view = DynamicModalView(**modal_config)
        form_data, modal_response = await modal_view.initiate_from_interaction(button_interaction)
        if not form_data:
            # If no form data is submitted, exit early
            return

        # Validate form data
        if not self._validate_event_form(form_data):
            msg = "Invalid event data. Please check the format of date and time fields."
            await display_content(modal_view, button_interaction, msg)
            return

        try:
            # Prepare timezone dropdown config for selection
            timezone_config = self.config["timezone_dropdown"].copy()
            timezone_config.pop("placeholder", None)
            # Get current timezone from event details
            current_tz = getattr(getattr(event.details.time, "tzinfo", None), "zone", "US/Eastern")
            for dropdown in timezone_config.get("dropdowns", []):
                if "options" in dropdown:
                    dropdown["selections"] = [
                        {**opt, "default": opt.get("value") == current_tz} for opt in dropdown.pop("options", [])
                    ]

            # Show timezone selection dropdown to user
            timezone_view = DynamicDropdownView(**timezone_config)
            timezone_data, dropdown_message = await timezone_view.initiate_from_message(
                modal_response or await button_interaction.original_response(),
                "Please select a timezone for the event:",
            )

            # Use selected timezone or fallback to current
            timezone = selected_tz(timezone_data, current_tz)

            # Parse and update event details
            event_time = parse_datetime(form_data["event_date"], form_data["event_time"], timezone)
            event.details.name = form_data["event_name"]
            event.details.description = form_data["event_description"]
            event.details.time = event_time
            event.details.location = form_data["event_location"]
            Database.update_document(event, {"details": event.details})

            # Notify user of success
            success_message = "Event updated successfully!"
            target_msg = dropdown_message or modal_response
            await display_content(target_msg, button_interaction, success_message)

            # Show updated event embed
            await self._show_event_embed(event, message)
        except Exception as e:
            # Handle and log any errors during update
            self.logger.error(f"Failed to update event: {e}", exc_info=True)
            error_message = f"Failed to update event: {e!s}"
            await display_content(modal_view, button_interaction, error_message)

    async def _get_prefilled__modal_config(self, event):
        """
        Get modal config with fields pre-filled from event details.
        """
        modal_config = self.config["edit_event_modal"].copy()
        for field in modal_config["modal"]["fields"]:
            match field["custom_id"]:
                case "event_name":
                    field["default"] = event.details.name
                case "event_description":
                    field["default"] = event.details.description
                case "event_date":
                    field["default"] = event.details.time.strftime("%m/%d/%y")
                case "event_time":
                    field["default"] = event.details.time.strftime("%I:%M %p")
                case "event_location":
                    field["default"] = event.details.location
        return modal_config

    async def _list_guild_events(self, interaction: discord.Interaction) -> None:
        """
        List events attributed to a guild
        """
        self.logger.info(f"Listing events for guild {interaction.guild_id}")

        # Retrieve guild from database
        guild = Database.get_document(Guild, interaction.guild_id)
        if not verify_guild_events(guild):
            self.logger.info(f"No events found for guild {interaction.guild_id}")
            await interaction.followup.send("No events found for this server.", ephemeral=True)
            return

        current_time = now()
        upcoming_events: list[Event] = []
        past_events: list[Event] = []

        self.logger.info(f"Found {len(guild.events)} events for guild {interaction.guild_id}")
        for event_id in guild.events:
            event = Database.get_document(Event, event_id)
            if event and hasattr(event, "details"):
                event_time = event.details.time
                # If the event time is offset-naive, assume UTC
                if event_time.tzinfo is None:
                    event_time = localize(event_time)
                if event_time >= current_time:
                    upcoming_events.append(event)
                else:
                    past_events.append(event)

        if all_false(upcoming_events, past_events):
            self.logger.info("No events found")
            await interaction.followup.send("No events found for this server.", ephemeral=True)
            return

        # Sort by datetime (soonest first), then list upcoming first, then past
        upcoming_events.sort(key=lambda e: e.details.time)
        past_events.sort(key=lambda e: e.details.time, reverse=True)

        total_count = len(upcoming_events) + len(past_events)
        embed = discord.Embed(
            title="Events",
            description=(f"Found {total_count} events (Upcoming: {len(upcoming_events)}, Past: {len(past_events)})"),
            color=discord.Color.blue(),
        )

        def add_event_field(ev: Event, is_old: bool) -> None:
            localized_time = self._format_datetime(ev.details.time)
            total_attendees = len(ev.yes_users)
            status_text = "OLD" if is_old else "UPCOMING"
            name_prefix = "[OLD] " if is_old else ""
            embed.add_field(
                name=f"{name_prefix}{ev.details.name} (ID: {ev._id})",
                value=(
                    f"**When:** {localized_time}\n"
                    f"**Where:** {ev.details.location}\n"
                    f"**Attendees:** {total_attendees}\n"
                    f"**Status:** {status_text}"
                ),
                inline=False,
            )

        for ev in upcoming_events:
            add_event_field(ev, is_old=False)
        for ev in past_events:
            add_event_field(ev, is_old=True)

        await interaction.followup.send(embed=embed, ephemeral=True)

    async def _show_event(self, interaction: discord.Interaction) -> None:
        """
        Show details of an event
        """
        # Interaction is already deferred
        event, message = await self._get_event_selection(interaction, Action.VIEW)
        if not event or not message:  # Check both event and message
            # Error/cancel message already handled within get_event_selection if possible
            return

        # Pass the message object to show_event_embed
        await self._show_event_embed(event, message)

    async def _show_user_events(self, interaction: discord.Interaction) -> None:
        """
        Show events a user is registered for
        """

        user = Database.get_document(User, interaction.user.id)
        if not verify_user_events(user):
            await interaction.followup.send("You're not registered for any events.", ephemeral=True)
            return

        # Get all events the user is registered for
        user_events = []
        current_time = now()

        for event_id in user.events:
            event = Database.get_document(Event, event_id)
            if verify_field(event, "details"):
                event_time = event.details.time
                # If the event time is offset-naive, assume it's in UTC
                if event_time.tzinfo is None:
                    event_time = localize(event_time)
                if event_time >= current_time:
                    user_events.append(event)

        if not user_events:
            await interaction.followup.send("You're not registered for any upcoming events.", ephemeral=True)
            return

        # Sort events by datetime
        user_events.sort(key=lambda e: e.details.time)

        # Create an embed to display the events
        embed = discord.Embed(
            title="Your Events",
            description=f"You are registered for {len(user_events)} upcoming events",
            color=discord.Color.green(),
        )

        for event in user_events:
            # Format date for display
            localized_time = self._format_datetime(event.details.time)

            # Determine registration status
            status = "Unknown"
            if interaction.user.id in event.yes_users:
                status = "✅ Attending"
            elif interaction.user.id in event.maybe_users:
                status = "❔ Maybe"

            # Add field for each event
            embed.add_field(
                name=event.details.name,
                value=(f"**When:** {localized_time}\n**Where:** {event.details.location}\n**Your Status:** {status}"),
                inline=False,
            )

        await interaction.followup.send(embed=embed, ephemeral=True)

    # TODO Someone that's in the database needs to test all RSVP options + myevents
    async def _announce_event(self, interaction: discord.Interaction) -> None:
        """
        Announce an event
        """

        # Get both event and the message from the dropdown interaction
        event, message = await self._get_event_selection(interaction, Action.ANNOUNCE)
        if not event or not message:  # Check both
            # Error/cancel message already handled within get_event_selection if possible
            return

        # Use the regular ConfirmView for confirmation
        view = ConfirmView(**self.config["confirm_announce"])

        try:
            await message.edit(  # Edit the message from the dropdown
                content=(
                    f"Are you sure you want to announce the event '{event.details.name}' in the announcements channel?"
                ),
                view=view,
                embed=None,
            )
        except (discord.NotFound, discord.HTTPException) as e:
            self.logger.warning(f"Failed to edit message for announce confirmation: {e}")
            return  # Can't proceed if message is gone

        await view.wait()

        # Check if announcement was cancelled early
        if not view.value:
            with suppress(discord.NotFound, discord.HTTPException):
                await message.edit(
                    content="Event announcement cancelled.",
                    view=None,
                    embed=None,  # Clear embed
                )  # Best effort
            return

        # Checking validity of interaction.guild for finding/creation of announcements channel
        if not interaction.guild:
            await message.edit(
                content="Error: This command must be used in a server.",
                view=None,
                embed=None,
            )
            return

        # Resolve announcements channel from server settings (fallback to name if not configured)
        guild_data = Database.get_document(Guild, interaction.guild.id)
        channel_id = getattr(getattr(guild_data, "channels", None), "announcements", None) if guild_data else None

        announcement_channel = get_announcement_channel(channel_id, interaction)

        if not announcement_channel:
            with suppress(discord.Forbidden, discord.HTTPException):
                await message.edit(
                    content=(
                        "Error: Announcements channel is not configured or found. "
                        "Use /server edit to set the 'Announcements Channel'."
                    ),
                    view=None,
                    embed=None,
                )
            return

        # Create announcement embed
        embed = discord.Embed(
            title=f"📅 Event: {event.details.name}",
            description=event.details.description,
            color=discord.Color.blue(),
        )

        # Add event details
        localized_time = self._format_datetime(event.details.time)
        embed.add_field(name="Date/Time", value=localized_time, inline=True)
        embed.add_field(name="Location", value=event.details.location, inline=True)

        # Add footer with instructions
        embed.set_footer(text="React with ✅ to attend, ❌ if you can't make it, or ❔ if you're unsure.")

        try:
            # Send the announcement
            announcement = await announcement_channel.send(embed=embed)

            # Add reactions
            add_reactions(announcement, ALLOWED_REACTIONS)

            # Save message ID to event
            event.message_id = announcement.id
            Database.update_document(event, {"message_id": announcement.id})

            # Update the original confirmation message
            await message.edit(
                content=f"Event announced in #{announcement_channel.name}!",
                view=None,
                embed=None,  # Clear embed
            )
        except discord.Forbidden:
            self.logger.error(f"Permission error announcing event {event._id} in channel {announcement_channel.id}")
            with suppress(discord.NotFound, discord.HTTPException):
                await message.edit(
                    content=(
                        "Error: I don't have permission to send messages or add reactions in the announcements channel."
                    ),
                    view=None,
                    embed=None,  # Clear embed
                )

    async def is_valid_reaction(self, payload):
        """
        Ensures the message reacted to is as a valid one
        """
        # Ignore bot reactions
        if not self.bot.user or payload.user_id == self.bot.user.id:
            return False, None, None

        # Check if this is a reaction to an event announcement
        channel = self.bot.get_channel(payload.channel_id)
        if not channel:
            return False, None, None

        # Fetch message to update the embed after processing
        message = await fetch_message_if_possible(channel, payload.message_id)
        if not message:
            return False, None, None

        return True, channel, message

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload) -> None:
        """
        Handles reactions added to announcement messages
        """
        valid, channel, message = await self.is_valid_reaction(payload)
        if not valid:
            return

        # Get Event
        event = await self._get_event_by_message_id(payload.message_id)
        if not event:
            return

        # Handle different reactions
        emoji = str(payload.emoji)
        user = self.bot.get_user(payload.user_id)

        # Ignore and remove any non-RSVP reactions
        if emoji not in ALLOWED_REACTIONS:
            # Attempt to remove the unsupported reaction for this user (if permitted)
            member = None
            if isinstance(channel, discord.TextChannel) and channel.guild:
                member = channel.guild.get_member(payload.user_id)
            target_user = member or user
            if target_user:
                with suppress(discord.NotFound, discord.Forbidden, discord.HTTPException):
                    await message.remove_reaction(payload.emoji, target_user)
            return

        # Remove any other reactions from this user on this message
        await remove_other_reactions(message, emoji, user)

        # Update event attendance based on reaction
        await self._handle_reaction_add(payload.user_id, event, emoji)

        # Update the announcement embed to reflect latest RSVP counts
        await self._show_event_embed(event, message)

    async def _get_event_by_message_id(self, message_id):
        """
        Gets the event linked to a certain announcement message
        """
        try:
            # Use MongoEngine directly for a query by message_id
            event = Event.objects(message_id=message_id).first()
            if not event:
                return
            return event
        except Exception as e:
            self.logger.error(f"Error finding event by message_id {message_id}: {e}")
            return

    async def _handle_reaction_add(self, user_id, event: Event, emoji):
        """
        Handles RSVP actions taken when a reaction is added
        """

        user = Database.get_document(User, user_id)
        if not user:
            self.logger.info(f"User {user_id} not registered; ignoring attendance add.")
            return

        vals: dict[RSVPEmoji, list[int]] = {
            RSVPEmoji.YES: event.yes_users,
            RSVPEmoji.MAYBE: event.maybe_users,
            RSVPEmoji.NO: event.no_users,
        }

        remove = build_removals(emoji)

        modified = False

        # Remove conflicting reactions by the user
        for reaction in remove:
            if user_id in vals[reaction]:
                vals[reaction].remove(user_id)
                event.details.reactions.modify(reaction.value, -1)
                modified = True

        # Add user to selected list if not already there
        if user_id not in vals[emoji]:
            vals[emoji].append(user_id)
            event.details.reactions.modify(emoji, 1)
            modified = True

        rsvp = RSVPEmoji.reverse(emoji)
        # Save the event document if modified
        if modified:
            event.save()
            self.logger.info(f"Updated event {event._id} for user {user_id} with '{rsvp.name}' response.")

        # Add event to user list if they fill yes or maybe, remove if they fill no
        if rsvp == RSVPEmoji.NO and hasattr(user, "events") and event._id in user.events:
            user.events.remove(event._id)
            user.save()
            self.logger.info(f"Removed event {event._id} from user {user_id}'s event list.")
        elif event._id not in user.events:
            user.events.append(event._id)
            user.save()
            self.logger.info(f"Updated user {user_id} for event {event._id} with '{rsvp.name}' response.")

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        """
        Handle reaction removal from event announcements.
        """
        valid, channel, message = await self.is_valid_reaction(payload)
        if not valid:
            return

        try:
            event = await self._get_event_by_message_id(payload.message_id)
            if not event:
                return
        except Exception as e:
            self.logger.error(f"Error finding event by message_id {payload.message_id}: {e}")
            return

        # Handle different reactions being removed
        emoji = str(payload.emoji)
        user_id = payload.user_id

        # Process the removal of reaction based on which emoji was removed
        self._handle_reaction_remove(event, user_id, emoji)

        # After updating RSVP state, refresh the embed with latest counts
        await self._show_event_embed(event, message)

    def _handle_reaction_remove(self, event, user_id, emoji):
        """
        Handles RSVP actions taken when a reaction is removed
        """
        rsvp = RSVPEmoji.reverse(emoji)

        vals: dict[RSVPEmoji, list[int]] = {
            RSVPEmoji.YES: event.yes_users,
            RSVPEmoji.MAYBE: event.maybe_users,
            RSVPEmoji.NO: event.no_users,
        }

        # Remove reaction from count
        if user_id in vals[rsvp]:
            vals[rsvp].remove(user_id)
            if all_true(event.details, event.details.reactions):
                event.details.reactions.modify(emoji, -1)
            modified = True

            if rsvp in {RSVPEmoji.YES, RSVPEmoji.MAYBE}:
                user = Database.get_document(User, user_id)
                if not user:
                    return
                still_positive = (user_id in event.yes_users) or (user_id in event.maybe_users)
                if not still_positive and hasattr(user, "events") and event._id in user.events:
                    user.events.remove(event._id)
                    user.save()
                    self.logger.info(
                        f"Removed event {event._id} from user {user_id}'s event list after reaction removal."
                    )
            if modified:
                event.save()
                self.logger.info(f"Updated event {event._id} for user {user_id} after reaction removal.")


async def setup(bot: commands.Bot) -> None:
    """
    Set up the Event cog.
    """
    await bot.add_cog(EventCog(bot))

"""Event management cog for handling events."""

import logging
import re
from contextlib import suppress
from datetime import UTC, datetime
from typing import Any

import discord
import pytz
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


class EventCog(commands.Cog):
    """Event management cog for handling guild events."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.logger = logging.getLogger(f"discord.cog.{self.__class__.__name__.lower()}")
        self.allowed_reactions = ["✅", "❌", "❔"]
        self.config = EVENT_CONFIG
        self.logger.info("Event cog initialized.")

    def now(self) -> datetime:
        """Returns current time in UTC."""
        return datetime.now(UTC)

    def parse_datetime(
        self, date_str: str, time_str: str, timezone_str: str | None = None
    ) -> datetime:
        """Parse date and time strings into a datetime object."""
        try:
            # Extract timezone from time string if not provided separately
            if timezone_str is None:
                time_parts_check = time_str.split()
                min_time_parts_with_tz = 2
                if len(time_parts_check) > min_time_parts_with_tz:
                    timezone_str = time_parts_check[-1]
                    time_str = " ".join(time_parts_check[:-1])
            # Default to Eastern Time if no timezone is specified
            if timezone_str is None:
                timezone_str = "US/Eastern"

            # Parse the date (expected format: MM/DD/YY)
            month, day, year = map(int, date_str.split("/"))
            two_digit_year_threshold = 100
            if year < two_digit_year_threshold:
                year = 2000 + year  # Convert 2-digit year to 4-digit

            # Parse the time (expected format: HH:MM AM/PM)
            time_parts = time_str.strip().split()
            hour, minute = map(int, time_parts[0].split(":"))

            # Adjust for AM/PM
            noon_hour = 12
            if time_parts[1].upper() == "PM" and hour < noon_hour:
                hour += noon_hour
            elif time_parts[1].upper() == "AM" and hour == noon_hour:
                hour = 0

            # Create datetime object
            dt = datetime(year, month, day, hour, minute)

            # Set the timezone
            tz = pytz.timezone(timezone_str)
            dt = tz.localize(dt) if dt.tzinfo is None else dt.astimezone(tz)

            return dt
        except Exception as e:
            self.logger.error(f"Error parsing date/time: {e}")
            raise ValueError(f"Invalid date/time format: {date_str} {time_str}") from e

    def format_datetime(self, dt: datetime, timezone_str: str = "US/Eastern") -> str:
        """Format a datetime object for display with timezone."""
        try:
            # Ensure datetime has timezone
            if dt.tzinfo is None:
                dt = pytz.UTC.localize(dt)

            # Convert to desired timezone
            target_tz = pytz.timezone(timezone_str)
            localized_dt = dt.astimezone(target_tz)

            # Format for display
            return localized_dt.strftime("%Y-%m-%d %I:%M %p %Z")
        except Exception as e:
            self.logger.error(f"Error formatting datetime: {e}")
            return str(dt)

    def _validate_event_form(self, form_data: dict[str, str]) -> bool:
        """Validate event form data."""
        # Check required fields
        required_fields = [
            "event_name",
            "event_date",
            "event_time",
            "event_location",
            "event_description",
        ]
        for field in required_fields:
            if field not in form_data or not form_data[field].strip():
                return False

        # Validate date format (MM/DD/YY)
        date_str = form_data.get("event_date", "")
        if not re.match(r"^(0[1-9]|1[0-2])/(0[1-9]|[12][0-9]|3[01])/\d{2}$", date_str):
            return False

        # Validate time format (HH:MM AM/PM)
        time_str = form_data.get("event_time", "")
        return (
            re.match(
                r"^(0?[1-9]|1[0-2]):([0-5][0-9])\s+(AM|PM)(\s+[A-Z]{2,4})?$",
                time_str,
                re.IGNORECASE,
            )
            is not None
        )

    # Register the /event command for the debug guild only
    @app_commands.guilds(
        discord.Object(id=settings.DEBUG_GUILD_ID if settings.DEBUG_GUILD_ID is not None else 0)
    )
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
        """Handle event actions based on user selection."""
        # Determine if the response should be deferred and if it should be ephemeral
        should_defer = action in ["list", "show", "announce", "myevents"]
        is_ephemeral = action in ["list", "show", "delete", "announce", "myevents"]

        if should_defer:
            await interaction.response.defer(ephemeral=is_ephemeral)

        # Route to the appropriate handler based on the action
        if action == "create":
            await self.create_event(interaction)
        elif action == "list":
            await self.list_events(interaction)
        elif action == "show":
            await self.show_event_selection(interaction)
        elif action == "edit":
            await self.edit_event_selection(interaction)
        elif action == "delete":
            await self._handle_delete_action(interaction)
        elif action == "announce":
            await self.announce_event_selection(interaction)
        elif action == "myevents":
            await self.my_events(interaction)

    async def _handle_delete_action(self, interaction: discord.Interaction) -> None:
        """Handle the delete action for events, checking for event existence first."""
        guild = Database.get_document(Guild, interaction.guild_id)
        # Check if the guild has any events
        if not guild or not hasattr(guild, "events") or not guild.events:
            await interaction.response.send_message(
                "No events found for this server.", ephemeral=True
            )
            return

        # Check if any events exist with details
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

        # Proceed to event deletion selection
        await self.delete_event_selection(interaction)

    async def create_event(self, interaction: discord.Interaction) -> None:
        """Handle event creation."""
        self.logger.info(f"Event creation requested by {interaction.user}")

        try:
            # Get event data from modal
            self.logger.info("Creating modal view")
            modal_view = DynamicModalView(**self.config["event_modal"])
            self.logger.info("Initiating modal interaction")
            event_data, modal_message = await modal_view.initiate_from_interaction(interaction)

            self.logger.info(
                f"Modal result: data={event_data is not None},"
                f"message exists={modal_message is not None}"
            )

            # Check if event data was submitted
            if not event_data:
                self.logger.info("No event data received, returning early")
                return

            # If modal view didn't return a message, create one using followup
            if not modal_message:
                modal_message = await interaction.followup.send(
                    "Processing event creation...", ephemeral=True, wait=True
                )

            # Validate the form data
            self.logger.info("Validating form data")
            if not self._validate_event_form(event_data):
                self.logger.info("Invalid form data")
                await modal_message.edit(
                    content="Invalid event data. Please check date/time formats and try again.",
                    view=None,
                )
                return

            self.logger.info("Form data validated successfully")

            # Get timezone selection
            timezone, dropdown_message = await self._get_timezone_selection(modal_message)

            # Parse the date and time into a datetime object
            event_time = self.parse_datetime(
                event_data["event_date"], event_data["event_time"], timezone
            )

            # Create and save the event
            new_event, event_id = await self._save_new_event(interaction, event_data, event_time)

            # Show the event details
            await self.show_event_embed(dropdown_message, new_event)
            self.logger.info(f"Event '{event_data['event_name']}' created with ID {event_id}")

        except Exception as e:
            self.logger.error(f"Exception in create_event: {e}", exc_info=True)
            if interaction.response.is_done():
                await interaction.followup.send(f"Error creating event: {e!s}", ephemeral=True)
            else:
                await interaction.response.send_message(
                    f"Error creating event: {e!s}", ephemeral=True
                )

    async def _get_timezone_selection(self, modal_message) -> tuple[str, Any]:
        """Helper to handle timezone selection dropdown."""
        self.logger.info("Creating timezone dropdown")
        timezone_config = self.config["timezone_dropdown"].copy()
        timezone_config.pop("placeholder", None)

        dropdowns = timezone_config.get("dropdowns", [])
        if isinstance(dropdowns, list):
            for dropdown in dropdowns:
                if isinstance(dropdown, dict) and "options" in dropdown:
                    dropdown["selections"] = dropdown.pop("options")
            timezone_config["dropdowns"] = dropdowns

        timezone_view = DynamicDropdownView(**timezone_config)
        timezone_data, dropdown_message = await timezone_view.initiate_from_message(
            modal_message, "Please select a timezone for the event:"
        )

        # If no timezone selection is returned, use helper to get default
        if not timezone_data or not timezone_data.get("timezone_selection"):
            self.logger.info("No timezone data received, attempting to use default from config")
            default_timezone = self._get_default_timezone()
            timezone_data = {"timezone_selection": [default_timezone]}

        timezone = timezone_data.get("timezone_selection", ["US/Eastern"])[0]
        return timezone, dropdown_message

    def _get_default_timezone(self) -> str:
        """Helper to get default timezone from config dropdowns."""
        fallback_dropdowns = self.config["timezone_dropdown"].get("dropdowns", [])
        for dropdown in fallback_dropdowns:
            options = dropdown.get("options", [])
            if isinstance(options, list):
                for option in options:
                    if isinstance(option, dict) and option.get("default"):
                        value = option.get("value")
                        if isinstance(value, str) and value:
                            return value
        return "US/Eastern"

    async def _save_new_event(self, interaction, event_data, event_time):
        """Helper to create and save a new event and update guild."""
        timezone = event_time.tzinfo.zone if event_time.tzinfo else "US/Eastern"
        tz = pytz.timezone(timezone)
        event_id = int(datetime.now(tz).timestamp() * 1000)
        new_event = Event(
            _id=event_id,
            guild_id=interaction.guild_id,
            yes_users=[],
            maybe_users=[],
            no_users=[],
            message_id=0,
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

    async def list_events(self, interaction: discord.Interaction) -> None:
        """List all events for the guild, labeling past events as OLD."""
        self.logger.info(f"Listing events for guild {interaction.guild_id}")

        guild = Database.get_document(Guild, interaction.guild_id)
        if not guild or not hasattr(guild, "events") or not guild.events:
            self.logger.info(f"No events found for guild {interaction.guild_id}")
            await interaction.followup.send("No events found for this server.", ephemeral=True)
            return

        current_time = self.now()
        upcoming_events: list[Event] = []
        past_events: list[Event] = []

        self.logger.info(f"Found {len(guild.events)} events for guild {interaction.guild_id}")
        for event_id in guild.events:
            event = Database.get_document(Event, event_id)
            if event and hasattr(event, "details"):
                event_time = event.details.time
                # If the event time is offset-naive, assume UTC
                if event_time.tzinfo is None:
                    event_time = pytz.UTC.localize(event_time)
                if event_time >= current_time:
                    upcoming_events.append(event)
                else:
                    past_events.append(event)

        if not upcoming_events and not past_events:
            self.logger.info("No events found")
            await interaction.followup.send("No events found for this server.", ephemeral=True)
            return

        # Sort by datetime (soonest first), then list upcoming first, then past
        upcoming_events.sort(key=lambda e: e.details.time)
        past_events.sort(key=lambda e: e.details.time, reverse=True)

        total_count = len(upcoming_events) + len(past_events)
        embed = discord.Embed(
            title="Events",
            description=(
                f"Found {total_count} events (Upcoming: {len(upcoming_events)}, Past: {len(past_events)})"
            ),
            color=discord.Color.blue(),
        )

        def add_event_field(ev: Event, is_old: bool) -> None:
            localized_time = self.format_datetime(ev.details.time)
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

    async def get_event_selection(
        self, interaction: discord.Interaction, action: str
    ) -> tuple[Event | None, discord.Message | None]:
        """Get event selection from dropdown. Returns (Event, Message) or (None, None)."""
        selected_event = None
        message = None
        error_msg = None
        try:
            # Get all events for the guild based on the action (e.g., delete, edit, view)
            guild_events = self._get_guild_events_for_action(interaction.guild_id, action)
            if not guild_events:
                # If no events found, set error message
                error_msg = self._get_event_error_msg(interaction.guild_id)
            else:
                # Build dropdown options and config for event selection
                options = self._build_event_dropdown_options(guild_events)
                dropdown_config = self._build_event_dropdown_config(options, action)
                view = DynamicDropdownView(**dropdown_config)
                # Show dropdown to user and get selection
                values, message = await self._get_dropdown_selection(interaction, view, action)
                if not values or not message:
                    # If no selection made, set error message
                    error_msg = "No event selected."
                else:
                    # Get selected event ID from either Upcoming or Old dropdown
                    selected_id_str = None
                    for key in (
                        "event_selection_upcoming",
                        "event_selection_old",
                        "event_selection",
                    ):
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
            return (None, message)
        # Return the selected event and message object
        return (selected_event, message)

    def _get_guild_events_for_action(self, guild_id, action):
        # Fetch the guild document from the database
        guild = Database.get_document(Guild, guild_id)
        if not guild or not hasattr(guild, "events") or not guild.events:
            # If no events found, return empty list
            return []
        current_time = self.now()
        events = []
        for event_id in getattr(guild, "events", []):
            event = Database.get_document(Event, event_id)
            if event and hasattr(event, "details"):
                event_time = event.details.time
                # If event time is naive, localize to UTC
                if event_time.tzinfo is None:
                    event_time = pytz.UTC.localize(event_time)
                # For delete, view, and edit include all events; otherwise, only future events
                if action in ("delete", "view", "edit") or event_time >= current_time:
                    events.append(event)
        return events

    def _get_event_error_msg(self, guild_id):
        # Helper to return appropriate error message for event selection
        guild = Database.get_document(Guild, guild_id)
        if not guild or not hasattr(guild, "events") or not guild.events:
            return "No events found for this server."
        return "No matching events found."

    def _build_event_dropdown_options(self, events):
        # Build grouped dropdown options: one for upcoming, one for old events
        current_time = self.now()
        upcoming: list[dict[str, str]] = []
        old: list[dict[str, str]] = []
        # Sort by time first so options are ordered
        def _event_time(ev: Event):
            t = ev.details.time
            return pytz.UTC.localize(t) if t.tzinfo is None else t
        try:
            sorted_events = sorted(events, key=lambda e: _event_time(e))
        except Exception:
            sorted_events = events
        for event in sorted_events:
            event_time = event.details.time
            if event_time.tzinfo is None:
                event_time = pytz.UTC.localize(event_time)
            is_old = event_time < current_time
            option = {
                "label": f"{'[OLD] ' if is_old else ''}{event.details.name}",
                "description": self.format_datetime(event.details.time)[:99],
                "value": str(event._id),
            }
            if is_old:
                old.append(option)
            else:
                upcoming.append(option)
        return {"upcoming": upcoming, "old": old}

    def _build_event_dropdown_config(self, options, action):
        # Build dropdown configuration for event selection view
        # If grouped options dict provided, render two dropdowns; else fallback to single
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

    async def _get_dropdown_selection(self, interaction, view, action):
        # Helper to show dropdown and get user selection
        values = None
        message = None
        try:
            if interaction.response.is_done():
                # If response is already sent, use followup message for dropdown
                message = await interaction.followup.send(
                    f"Please select an event to {action}:",
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
                        content=f"Event selection for {action} was cancelled.",
                        view=None,
                        embed=None,
                    )
                    return None, message
            else:
                # If response not sent, initiate dropdown from interaction
                values, message = await view.initiate_from_interaction(
                    interaction, f"Please select an event to {action}:"
                )
        except (discord.NotFound, discord.HTTPException) as e:
            # Log and return None on interaction/HTTP errors
            self.logger.warning(f"Interaction/HTTP error during event selection for {action}: {e}")
            return None, message
        except Exception as e:
            # Log and return None on unexpected errors
            self.logger.error(
                f"Unexpected error during dropdown view handling: {e}",
                exc_info=True,
            )
            return None, message
        # If user did not accept selection, handle timeout/cancel
        if not getattr(view, "accepted", False):
            if getattr(view, "_timed_out", False):
                await message.edit(content="Event selection timed out.", view=None, embed=None)
            else:
                await message.edit(content="Event selection cancelled.", view=None, embed=None)
            return None, message
        # Return selected values and message object
        return values, message

    async def _send_event_selection_error(self, interaction, error_msg, message=None):
        """Helper to send error message for event selection and reduce return statements."""
        if message:
            # If a message object is provided, try to edit it with the error message
            with suppress(discord.NotFound, discord.HTTPException):
                await message.edit(
                    content=error_msg,
                    view=None,
                    embed=None,
                )
        else:
            # If no message object, send the error as a followup or initial response
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

    async def show_event_selection(self, interaction: discord.Interaction) -> None:
        """Show details of a specific event selected from dropdown."""
        # Interaction already deferred
        event, message = await self.get_event_selection(interaction, "view")
        if not event or not message:  # Check both event and message
            # Error/cancel message already handled within get_event_selection if possible
            return

        # Pass the message object to show_event_embed
        await self.show_event_embed(message, event)

    async def edit_event_selection(self, interaction: discord.Interaction) -> None:
        """Edit a specific event selected from dropdown."""
        event, message = await self.get_event_selection(interaction, "edit")
        if not event or not message:
            # If no event or message is returned, exit early
            return

        view = EditView(
            lambda button_interaction: self._handle_edit_event_button(
                button_interaction, event, message
            ),
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

    async def _handle_edit_event_button(
        self, button_interaction: discord.Interaction, event: Event, message: discord.Message
    ) -> None:
        """Helper for edit_event_selection to handle the edit button logic."""
        modal_config = await self.get_prefilled__modal_config(event)
        modal_view = DynamicModalView(**modal_config)
        form_data, modal_response = await modal_view.initiate_from_interaction(button_interaction)
        if not form_data:
            # If no form data is submitted, exit early
            return

        if not self._validate_event_form(form_data):
            # If form data is invalid, notify the user
            msg = "Invalid event data. Please check the format of date and time fields."
            if modal_response:
                await modal_response.edit(content=msg, view=None)
            else:
                await button_interaction.followup.send(msg, ephemeral=True)
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
                        {**opt, "default": opt.get("value") == current_tz}
                        for opt in dropdown.pop("options", [])
                    ]

            # Show timezone selection dropdown to user
            timezone_view = DynamicDropdownView(**timezone_config)
            timezone_data, dropdown_message = await timezone_view.initiate_from_message(
                modal_response or await button_interaction.original_response(),
                "Please select a timezone for the event:",
            )
            # Use selected timezone or fallback to current
            timezone = (
                timezone_data.get("timezone_selection", [current_tz])[0]
                if timezone_data and timezone_data.get("timezone_selection")
                else current_tz
            )

            # Parse and update event details
            event_time = self.parse_datetime(
                form_data["event_date"], form_data["event_time"], timezone
            )
            event.details.name = form_data["event_name"]
            event.details.description = form_data["event_description"]
            event.details.time = event_time
            event.details.location = form_data["event_location"]
            Database.update_document(event, {"details": event.details})

            # Notify user of success
            success_message = "Event updated successfully!"
            target_msg = dropdown_message or modal_response
            if target_msg:
                await target_msg.edit(content=success_message, view=None)
            else:
                await button_interaction.followup.send(content=success_message, ephemeral=True)

            # Show updated event embed
            await self.show_event_embed(message, event)

        except Exception as e:
            # Handle and log any errors during update
            self.logger.error(f"Failed to update event: {e}", exc_info=True)
            error_message = f"Failed to update event: {e!s}"
            if modal_response:
                await modal_response.edit(content=error_message, view=None)
            else:
                await button_interaction.followup.send(content=error_message, ephemeral=True)

    async def delete_event_selection(self, interaction: discord.Interaction) -> None:
        """Delete a specific event selected from dropdown."""
        event, message = await self.get_event_selection(interaction, "delete")
        if not event or not message:
            # If no event or message is returned, exit early
            return

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

    async def _show_delete_confirmation(self, message, event):
        """Show confirmation dialog and return True/False/None (timeout)."""
        view = ConfirmDeleteView()
        try:
            # Edit message to show confirmation dialog
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
        # Return user's confirmation choice (True/False/None)
        return view.value

    async def _delete_event_and_cleanup(self, event, guild_id):
        """Remove event from guild, users, and database. Returns error if any."""
        # Remove event from guild's events list
        try:
            guild = Database.get_document(Guild, guild_id)
            if guild and hasattr(guild, "events") and event._id in guild.events:
                guild.events.remove(event._id)
                Database.update_document(guild, {"events": guild.events})
                self.logger.info(f"Removed event {event._id} from guild {guild_id}")
        except Exception as e:
            self.logger.error(f"Error removing event {event._id} from guild: {e}")
        # Remove event from users' event lists
        all_users = (
            set(getattr(event, "yes_users", []))
            | set(getattr(event, "maybe_users", []))
            | set(getattr(event, "no_users", []))
        )
        for user_id in all_users:
            try:
                user = Database.get_document(User, user_id)
                if user and hasattr(user, "events") and event._id in user.events:
                    user.events.remove(event._id)
                    user.save()
                    self.logger.info(f"Removed event {event._id} from user {user_id}'s events")
            except Exception as e:
                self.logger.error(f"Error removing event {event._id} from user {user_id}: {e}")
        # Delete the event from the database
        try:
            Database.delete_document(event)
            self.logger.info(f"Event {event._id} '{event.details.name}' deleted")
            return None
        except Exception as e:
            self.logger.error(f"Error deleting event {event._id}: {e}")
            return e

    async def _edit_message_safe(self, message, content):
        """Safely edit a message, suppressing common exceptions."""
        with suppress(discord.NotFound, discord.HTTPException):
            await message.edit(content=content, view=None, embed=None)

    async def announce_event_selection(self, interaction: discord.Interaction) -> None:
        """Announce a specific event selected from dropdown."""
        # Get both event and the message from the dropdown interaction
        event, message = await self.get_event_selection(interaction, "announce")
        if not event or not message:  # Check both
            # Error/cancel message already handled within get_event_selection if possible
            return

        # Use the regular ConfirmView for confirmation
        view = ConfirmView(**self.config["confirm_announce"])

        try:
            await message.edit(  # Edit the message from the dropdown
                content=(
                    f"Are you sure you want to announce the event '{event.details.name}' "
                    "in the announcements channel?"
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

        # Checking valididty of interaction.guild for finding/creation of announcements channel
        if not interaction.guild:
            await message.edit(
                content="Error: This command must be used in a server.",
                view=None,
                embed=None,
            )
            return

        # Find or create announcements channel
        announcement_channel = discord.utils.get(
            interaction.guild.text_channels, name="announcements"
        )  # Use your actual channel name

        if not announcement_channel:
            with suppress(discord.Forbidden, discord.HTTPException):
                await message.edit(
                    content="Error: Could not find or create the announcements channel.",
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
        localized_time = self.format_datetime(event.details.time)
        embed.add_field(name="Date/Time", value=localized_time, inline=True)
        embed.add_field(name="Location", value=event.details.location, inline=True)

        # Add footer with instructions
        embed.set_footer(
            text="React with ✅ to attend, ❌ if you can't make it, or ❔ if you're unsure."
        )

        try:
            # Send the announcement
            announcement = await announcement_channel.send(embed=embed)

            # Add reactions
            for reaction in self.allowed_reactions:
                await announcement.add_reaction(reaction)

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
            self.logger.error(
                f"Permission error announcing event {event._id} "
                f"in channel {announcement_channel.id}"
            )
            with suppress(discord.NotFound, discord.HTTPException):
                await message.edit(
                    content=(
                        "Error: I don't have permission to send messages or add reactions "
                        "in the announcements channel."
                    ),
                    view=None,
                    embed=None,  # Clear embed
                )
        except Exception as e:
            self.logger.error(f"Error during event announcement send/react: {e}", exc_info=True)
            with suppress(discord.NotFound, discord.HTTPException):
                await message.edit(
                    content="An error occurred while sending the announcement.",
                    view=None,
                    embed=None,  # Clear embed
                )

    async def my_events(self, interaction: discord.Interaction) -> None:
        """Show events the user is registered for with registration status."""
        user = Database.get_document(User, interaction.user.id)
        if not user or not hasattr(user, "events") or not user.events:
            await interaction.followup.send("You're not registered for any events.", ephemeral=True)
            return

        # Get all events the user is registered for
        user_events = []
        current_time = self.now()

        for event_id in user.events:
            event = Database.get_document(Event, event_id)
            if event and hasattr(event, "details"):
                event_time = event.details.time
                # If the event time is offset-naive, assume it's in UTC
                if event_time.tzinfo is None:
                    event_time = pytz.UTC.localize(event_time)
                if event_time >= current_time:
                    user_events.append(event)

        if not user_events:
            await interaction.followup.send(
                "You're not registered for any upcoming events.", ephemeral=True
            )
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
            localized_time = self.format_datetime(event.details.time)

            # Determine registration status
            status = "Unknown"
            if interaction.user.id in event.yes_users:
                status = "✅ Attending"
            elif interaction.user.id in event.maybe_users:
                status = "❔ Maybe"

            # Add field for each event
            embed.add_field(
                name=event.details.name,
                value=(
                    f"**When:** {localized_time}\n"
                    f"**Where:** {event.details.location}\n"
                    f"**Your Status:** {status}"
                ),
                inline=False,
            )

        await interaction.followup.send(embed=embed, ephemeral=True)

    async def show_event_embed(
        self,
        message_or_interaction: discord.Message | discord.Interaction,
        event: Event,
    ) -> None:
        """Display event details in an embed."""

        # Determine if the event is old (in the past)
        current_time = self.now()
        event_time = event.details.time
        if event_time.tzinfo is None:
            event_time = pytz.UTC.localize(event_time)
        is_old = event_time < current_time

        # Create the embed, tinting red for old events
        title_prefix = "[OLD] " if is_old else ""
        embed = discord.Embed(
            title=f"{title_prefix}{event.details.name}",
            description=event.details.description,
            color=discord.Color.red() if is_old else discord.Color.purple(),
        )

        # Add event details
        localized_time = self.format_datetime(event.details.time)
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

        # Narrow type for mypy
        if isinstance(message_or_interaction, discord.Message):
            await message_or_interaction.edit(content=None, embed=embed, view=None)
        elif isinstance(message_or_interaction, discord.Interaction):
            await message_or_interaction.followup.send(embed=embed, ephemeral=True)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload) -> None:
        """Handle reactions to event announcements."""
        # Ignore bot reactions
        if not self.bot.user or payload.user_id == self.bot.user.id:
            return

        # Check if this is a reaction to an event announcement
        channel = self.bot.get_channel(payload.channel_id)
        if not channel:
            return

        message = await self.fetch_message_if_possible(channel, payload.message_id)
        if not message:
            return

        event = await self.get_event_by_message_id(payload.message_id)
        if not event:
            return

        # Handle different reactions
        emoji = str(payload.emoji)
        user = self.bot.get_user(payload.user_id)

        # Remove any other reactions from this user on this message
        await self.remove_other_reactions(message, emoji, user)
        # Update event attendance based on reaction
        if emoji == "✅":
            await self.handle_attendance_add(payload.user_id, event)
        elif emoji == "❌":
            await self.handle_attendance_remove(payload.user_id, event)
        elif emoji == "❔":
            await self.handle_attendance_maybe(payload.user_id, event)

    async def fetch_message_if_possible(self, channel: discord.TextChannel, message_id):
        if isinstance(channel, (discord.TextChannel | discord.Thread)):
            with suppress(discord.NotFound, discord.Forbidden):
                return await channel.fetch_message(message_id)
        return None

    async def get_event_by_message_id(self, message_id):
        try:
            # Use MongoEngine directly for a query by message_id
            event = Event.objects(message_id=message_id).first()
            if not event:
                return
        except Exception as e:
            self.logger.error(f"Error finding event by message_id {message_id}: {e}")
            return

    async def remove_other_reactions(self, message, emoji, user):
        for reaction in message.reactions:
            if str(reaction.emoji) != emoji and user:
                with suppress(discord.NotFound, discord.HTTPException):
                    await reaction.remove(user)

    async def handle_attendance_add(self, user_id: int, event: Event) -> None:
        """Handle adding a user to event attendance with "yes" response."""
        user = Database.get_document(User, user_id)

        if not user:
            self.logger.info(f"User {user_id} not registered; ignoring attendance add.")
            return

        # Remove user from other RSVP lists
        modified = await self._remove_user_from_rsvp_lists(user_id, event)

        # Add user to yes_users list if not already there
        if user_id not in event.yes_users:
            event.yes_users.append(user_id)
            if event.details and event.details.reactions:
                event.details.reactions.yes += 1
            modified = True

        # Save the event document if modified
        if modified:
            event.save()
            self.logger.info(f"Updated event {event._id} for user {user_id} with 'yes' response.")

        # Handle user document updates
        if not hasattr(user, "events"):
            user.events = []

        # Ensure event is in user's list
        if event._id not in user.events:
            user.events.append(event._id)
            user.save()
            self.logger.info(f"Updated user {user_id} for event {event._id} with 'yes' response.")

    async def _remove_user_from_rsvp_lists(self, user_id: int, event: Event) -> bool:
        """
        Helper to remove user from maybe_users and no_users RSVP lists.
        Returns True if any modification was made.
        """
        modified = False
        # Remove user from maybe_users if present
        if user_id in event.maybe_users:
            event.maybe_users.remove(user_id)
            # Decrement maybe reaction count, ensuring it doesn't go below zero
            if event.details and event.details.reactions:
                event.details.reactions.maybe = max(0, event.details.reactions.maybe - 1)
            modified = True
        # Remove user from no_users if present
        if user_id in event.no_users:
            event.no_users.remove(user_id)
            # Decrement no reaction count, ensuring it doesn't go below zero
            if event.details and event.details.reactions:
                event.details.reactions.no = max(0, event.details.reactions.no - 1)
            modified = True
        # Return whether any RSVP list was modified
        return modified

    async def handle_attendance_remove(self, user_id: int, event: Event) -> None:
        """Handle marking a user with "no" response (not attending)."""
        user = Database.get_document(User, user_id)

        if not user:
            self.logger.info(f"User {user_id} not registered; ignoring attendance removal.")
            return

        # Create a copy of the event to modify
        modified = False

        # First, check if the user is in any of the other lists and remove them
        # Remove from yes_users if present
        if user_id in event.yes_users:
            event.yes_users.remove(user_id)
            if event.details and event.details.reactions:
                event.details.reactions.yes = max(0, event.details.reactions.yes - 1)
            modified = True

        # Remove from maybe_users if present
        if user_id in event.maybe_users:
            event.maybe_users.remove(user_id)
            if event.details and event.details.reactions:
                event.details.reactions.maybe = max(0, event.details.reactions.maybe - 1)
            modified = True

        # Add user to no_users list if not already there
        if user_id not in event.no_users:
            event.no_users.append(user_id)
            if event.details and event.details.reactions:
                event.details.reactions.no += 1
            modified = True

        # Save the event document if modified
        if modified:
            event.save()
            self.logger.info(f"Updated event {event._id} for user {user_id} with 'no' response.")

        # Handle user document updates
        # A "no" response means removing the event from the user's list
        if hasattr(user, "events") and event._id in user.events:
            user.events.remove(event._id)
            user.save()
            self.logger.info(f"Removed event {event._id} from user {user_id}'s event list.")

    async def handle_attendance_maybe(self, user_id: int, event: Event) -> None:
        """Handle marking a user as maybe for event attendance."""
        user = Database.get_document(User, user_id)

        if not user:
            self.logger.info(f"User {user_id} not registered; ignoring maybe attendance.")
            return

        # Create a copy of the event to modify
        modified = False

        # First, check if the user is in any of the other lists and remove them
        # Remove from yes_users if present
        if user_id in event.yes_users:
            event.yes_users.remove(user_id)
            if event.details and event.details.reactions:
                event.details.reactions.yes = max(0, event.details.reactions.yes - 1)
            modified = True

        # Remove from no_users if present
        if user_id in event.no_users:
            event.no_users.remove(user_id)
            if event.details and event.details.reactions:
                event.details.reactions.no = max(0, event.details.reactions.no - 1)
            modified = True

        # Add user to maybe_users list if not already there
        if user_id not in event.maybe_users:
            event.maybe_users.append(user_id)
            if event.details and event.details.reactions:
                event.details.reactions.maybe += 1
            modified = True

        # Save the event document if modified
        if modified:
            event.save()
            self.logger.info(f"Updated event {event._id} for user {user_id} with 'maybe' response.")

        # Add event to user list if they fill maybe
        if event._id not in user.events:
            user.events.append(event._id)
            user.save()
            self.logger.info(f"Updated user {user_id} for event {event._id} with 'maybe' response.")

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload) -> None:
        """Handle reaction removal from event announcements."""
        # Ignore bot reactions
        if not self.bot.user or payload.user_id == self.bot.user.id:
            return

        # Check if this is a reaction to an event announcement
        channel = self.bot.get_channel(payload.channel_id)
        if not channel:
            return

        try:
            event = Database.get_document(Event, payload.message_id)
            if not event:
                return
        except Exception as e:
            self.logger.error(f"Error finding event by message_id {payload.message_id}: {e}")
            return

        # Handle different reactions being removed
        emoji = str(payload.emoji)
        user_id = payload.user_id

        # Process the removal of reaction based on which emoji was removed
        if emoji == "✅":
            await self.handle_yes_reaction_remove(event, user_id)
        elif emoji == "❌":
            await self.handle_no_reaction_remove(event, user_id)
        elif emoji == "❔":
            await self.handle_maybe_reaction_remove(event, user_id)

    async def remove_event_from_user(self, event, user_id):
        # Remove event from user's list
        user = Database.get_document(User, user_id)
        if user and hasattr(user, "events") and event._id in user.events:
            user.events.remove(event._id)
            user.save()
            self.logger.info(
                f"Removed event {event._id}"
                f"from user {user_id}'s event list after maybe reaction removal."
            )

    async def handle_yes_reaction_remove(self, event, user_id):
        # Process the removal of reaction For "yes" response
        modified = False
        if user_id in event.yes_users:
            # Remove from yes list
            event.yes_users.remove(user_id)
            if event.details and event.details.reactions:
                event.details.reactions.yes = max(0, event.details.reactions.yes - 1)
            modified = True
            await self.remove_event_from_user(event, user_id)
        if modified:
            event.save()
            self.logger.info(
                f"Updated event {event._id} for user {user_id} after reaction removal."
            )

    async def handle_no_reaction_remove(self, event, user_id):
        # Process the removal of reaction For "no" response
        modified = False
        if user_id in event.no_users:
            # Remove from no list
            event.no_users.remove(user_id)
            if event.details and event.details.reactions:
                event.details.reactions.no = max(0, event.details.reactions.no - 1)
            modified = True
        if modified:
            event.save()
            self.logger.info(
                f"Updated event {event._id} for user {user_id} after reaction removal."
            )

    async def handle_maybe_reaction_remove(self, event, user_id):
        # Process the removal of reaction For "maybe" response
        modified = False
        if user_id in event.maybe_users:
            # Remove from maybe list
            event.maybe_users.remove(user_id)
            if event.details and event.details.reactions:
                event.details.reactions.maybe = max(0, event.details.reactions.maybe - 1)
            modified = True
            await self.remove_event_from_user(event, user_id)
        if modified:
            event.save()
            self.logger.info(
                f"Updated event {event._id} for user {user_id} after maybe reaction removal."
            )

    async def get_prefilled__modal_config(self, event: Event) -> dict:
        """Return modal config with fields pre-filled from event details."""
        modal_config = self.config["edit_event_modal"].copy()
        for field in modal_config["modal"]["fields"]:
            if field["custom_id"] == "event_name":
                field["default"] = event.details.name
            elif field["custom_id"] == "event_description":
                field["default"] = event.details.description
            elif field["custom_id"] == "event_date":
                field["default"] = event.details.time.strftime("%m/%d/%y")
            elif field["custom_id"] == "event_time":
                field["default"] = event.details.time.strftime("%I:%M %p")
            elif field["custom_id"] == "event_location":
                field["default"] = event.details.location
        return modal_config


async def setup(bot: commands.Bot) -> None:
    """Set up the Event cog."""
    await bot.add_cog(EventCog(bot))

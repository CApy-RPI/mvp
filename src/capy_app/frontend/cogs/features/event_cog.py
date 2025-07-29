"""Event management cog for handling events."""

import logging
import re
from contextlib import suppress
from datetime import UTC, datetime

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

    @app_commands.guilds(discord.Object(id=settings.DEBUG_GUILD_ID))
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
        """Handle event actions."""
        should_defer = action in ["list", "show", "announce", "myevents"]
        is_ephemeral = action in ["list", "show", "delete", "announce", "myevents"]

        if should_defer:
            await interaction.response.defer(ephemeral=is_ephemeral)

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
        """Handle the delete action for events."""
        guild = Database.get_document(Guild, interaction.guild_id)
        if not guild or not hasattr(guild, "events") or not guild.events:
            await interaction.response.send_message(
                "No events found for this server.", ephemeral=True
            )
            return

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

    async def _get_timezone_selection(self, modal_message) -> tuple[str, any]:
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
        """List all upcoming events for the guild."""
        self.logger.info(f"Listing events for guild {interaction.guild_id}")

        guild = Database.get_document(Guild, interaction.guild_id)
        if not guild or not hasattr(guild, "events") or not guild.events:
            self.logger.info(f"No events found for guild {interaction.guild_id}")
            await interaction.followup.send("No events found for this server.", ephemeral=True)
            return

        # Get all upcoming events from guild's event list
        current_time = self.now()
        guild_events = []

        self.logger.info(f"Found {len(guild.events)} events for guild {interaction.guild_id}")
        for event_id in guild.events:
            event = Database.get_document(Event, event_id)
            if event and hasattr(event, "details"):
                event_time = event.details.time
                # If the event time is offset-naive,
                # assume it's in UTC (or use another default timezone)
                if event_time.tzinfo is None:
                    event_time = pytz.UTC.localize(event_time)
                if event_time >= current_time:
                    guild_events.append(event)

        if not guild_events:
            self.logger.info("No upcoming events found")
            await interaction.followup.send("No upcoming events found.", ephemeral=True)
            return

        # Sort events by datetime
        guild_events.sort(key=lambda e: e.details.time)

        # Create an embed to display the events
        embed = discord.Embed(
            title="Upcoming Events",
            description=f"Found {len(guild_events)} upcoming events",
            color=discord.Color.blue(),
        )

        for event in guild_events:
            # Format date for display
            localized_time = self.format_datetime(event.details.time)

            # Count total attendees from yes_users list
            total_attendees = len(event.yes_users)

            # Add field for each event
            embed.add_field(
                name=f"{event.details.name} (ID: {event._id})",
                value=(
                    f"**When:** {localized_time}\n"
                    f"**Where:** {event.details.location}\n"
                    f"**Attendees:** {total_attendees}"
                ),
                inline=False,
            )

        await interaction.followup.send(embed=embed, ephemeral=True)

    async def get_event_selection(
        self, interaction: discord.Interaction, action: str
    ) -> tuple[Event | None, discord.Message | None]:
        """Get event selection from dropdown. Returns (Event, Message) or (None, None)."""
        message: discord.Message | None = None
        error_msg = None
        guild_events: list = []
        result: tuple = (None, None)
        try:
            guild = Database.get_document(Guild, interaction.guild_id)
            if not guild or not hasattr(guild, "events") or not guild.events:
                error_msg = "No events found for this server."
            else:
                current_time = self.now()
                for event_id in getattr(guild, "events", []):
                    event = Database.get_document(Event, event_id)
                    if event and hasattr(event, "details"):
                        event_time = event.details.time
                        if event_time.tzinfo is None:
                            event_time = pytz.UTC.localize(event_time)
                        if action == "delete" or event_time >= current_time:
                            guild_events.append(event)
                if not guild_events:
                    error_msg = "No matching events found."
            if error_msg:
                await self._send_event_selection_error(interaction, error_msg)
                return result

            options = [
                {
                    "label": f"{event.details.name}",
                    "description": self.format_datetime(event.details.time)[:99],
                    "value": str(event._id),
                }
                for event in guild_events
            ]
            dropdown_config = {
                "ephemeral": True,
                "buttons": (True, True),
                "timeout": 180,
                "dropdowns": [
                    {
                        "custom_id": "event_selection",
                        "placeholder": f"Select an event to {action}",
                        "min_values": 1,
                        "max_values": 1,
                        "selections": options,
                    }
                ],
            }
            view = DynamicDropdownView(**dropdown_config)
            values = None
            try:
                if interaction.response.is_done():
                    message = await interaction.followup.send(
                        f"Please select an event to {action}:",
                        view=view,
                        ephemeral=True,
                        wait=True,
                    )
                    await view.wait()
                    selections = {}
                    for dropdown in getattr(view, "_dropdowns", []):
                        if hasattr(dropdown, "selected_values") and dropdown.selected_values:
                            selections[getattr(dropdown, "custom_id", "event_selection")] = (
                                dropdown.selected_values
                            )
                    values = selections if getattr(view, "accepted", False) else None
                    if hasattr(view, "cancelled") and getattr(view, "cancelled", False):
                        await message.edit(
                            content=f"Event selection for {action} was cancelled.",
                            view=None,
                            embed=None,
                        )
                        error_msg = "Event selection cancelled."
                else:
                    values, message = await view.initiate_from_interaction(
                        interaction, f"Please select an event to {action}:"
                    )
            except (discord.NotFound, discord.HTTPException) as e:
                self.logger.warning(
                    f"Interaction/HTTP error during event selection for {action}: {e}"
                )
                error_msg = "Event selection failed."
            except Exception as e:
                self.logger.error(
                    f"Unexpected error during dropdown view handling: {e}",
                    exc_info=True,
                )
                error_msg = "Event selection failed."

            # Defensive: ensure message and values are defined
            if error_msg or not getattr(view, "accepted", False) or not values or not message:
                if not error_msg:
                    if not getattr(view, "accepted", False) and getattr(view, "_timed_out", False):
                        error_msg = "Event selection timed out."
                    elif not getattr(view, "accepted", False):
                        error_msg = "Event selection cancelled."
                    elif not values:
                        error_msg = "No event selected."
                    elif not message:
                        error_msg = "Event selection failed."
                    else:
                        error_msg = "Event selection cancelled."
                await self._send_event_selection_error(interaction, error_msg, message)
                return result

            selected_id_str = values.get("event_selection", [None])[0]
            if not selected_id_str:
                error_msg = "No event selected."
                await self._send_event_selection_error(interaction, error_msg, message)
                return result

            try:
                selected_id = int(selected_id_str)
            except ValueError:
                error_msg = f"Error: Invalid event ID selected ({selected_id_str})."
                await self._send_event_selection_error(interaction, error_msg, message)
                return result

            selected_event = Database.get_document(Event, selected_id)
            if not selected_event:
                error_msg = f"Error: Event with ID {selected_id} not found."
                await self._send_event_selection_error(interaction, error_msg, message)
                return (None, message)
            return (selected_event, message)
        except Exception as e:
            self.logger.error(f"Outer error in get_event_selection: {e!s}", exc_info=True)
            error_msg = "An unexpected error occurred while selecting the event."
            await self._send_event_selection_error(interaction, error_msg)
            return result

    async def _send_event_selection_error(self, interaction, error_msg, message=None):
        """Helper to send error message for event selection and reduce return statements."""
        if message:
            with suppress(discord.NotFound, discord.HTTPException):
                await message.edit(
                    content=error_msg,
                    view=None,
                    embed=None,
                )
        else:
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(error_msg, ephemeral=True)
                else:
                    await interaction.response.send_message(error_msg, ephemeral=True)
            except (discord.NotFound, discord.HTTPException):
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
        # Prompt the user to select an event to edit
        event, message = await self.get_event_selection(interaction, "edit")
        if not event or not message:
            # Error/cancel message already handled within get_event_selection if possible
            return

        # Define the callback for when the "Edit" button is pressed
        async def handle_edit_button(button_interaction: discord.Interaction) -> None:
            # Get a modal config with fields pre-filled from the selected event
            modal_config = await self.get_prefilled__modal_config(event)

            # Show the modal to the user and wait for their input
            modal_view = DynamicModalView(**modal_config)
            form_data, modal_response = await modal_view.initiate_from_interaction(
                button_interaction
            )
            if not form_data:
                return

            # Validate the submitted form data
            if not self._validate_event_form(form_data):
                msg = "Invalid event data. Please check the format of date and time fields."
                if modal_response:
                    await modal_response.edit(content=msg, view=None)
                else:
                    await button_interaction.followup.send(msg, ephemeral=True)
                return

            try:
                # Prepare the timezone dropdown config,
                # setting the current event timezone as default
                timezone_config = self.config["timezone_dropdown"].copy()
                timezone_config.pop("placeholder", None)
                current_tz = getattr(
                    getattr(event.details.time, "tzinfo", None), "zone", "US/Eastern"
                )
                for dropdown in timezone_config.get("dropdowns", []):
                    if "options" in dropdown:
                        dropdown["selections"] = [
                            {**opt, "default": opt.get("value") == current_tz}
                            for opt in dropdown.pop("options", [])
                        ]

                # Show the timezone dropdown to the user
                timezone_view = DynamicDropdownView(**timezone_config)
                timezone_data, dropdown_message = await timezone_view.initiate_from_message(
                    modal_response or await button_interaction.original_response(),
                    "Please select a timezone for the event:",
                )
                timezone = (
                    timezone_data.get("timezone_selection", [current_tz])[0]
                    if timezone_data and timezone_data.get("timezone_selection")
                    else current_tz
                )

                # Parse the new date and time with the selected timezone
                event_time = self.parse_datetime(
                    form_data["event_date"], form_data["event_time"], timezone
                )

                # Update the event details with the new data
                event.details.name = form_data["event_name"]
                event.details.description = form_data["event_description"]
                event.details.time = event_time
                event.details.location = form_data["event_location"]
                Database.update_document(event, {"details": event.details})

                # Notify the user of success
                success_message = "Event updated successfully!"
                target_msg = dropdown_message or modal_response
                if target_msg:
                    await target_msg.edit(content=success_message, view=None)
                else:
                    await button_interaction.followup.send(content=success_message, ephemeral=True)

                # Show the updated event embed
                await self.show_event_embed(message, event)

            except Exception as e:
                self.logger.error(f"Failed to update event: {e}", exc_info=True)
                error_message = f"Failed to update event: {e!s}"
                if modal_response:
                    await modal_response.edit(content=error_message, view=None)
                else:
                    await button_interaction.followup.send(content=error_message, ephemeral=True)

        # Show the edit/cancel button view to the user
        view = EditView(handle_edit_button, ephemeral=True)
        await message.edit(
            content='Press "Edit" below to edit this event or press "Cancel" to cancel editing:',
            view=view,
        )
        await view.wait()
        # If the user cancels, update the message accordingly
        if view.value is False:
            with suppress(discord.NotFound, discord.HTTPException):
                await message.edit(
                    content="Event editing cancelled.",
                    view=None,
                    embed=None,
                )

    async def delete_event_selection(self, interaction: discord.Interaction) -> None:
        """Delete a specific event selected from dropdown."""
        # Get both event and the message from the dropdown interaction
        event, message = await self.get_event_selection(interaction, "delete")
        if not event or not message:  # Check both
            # Error/cancel message already handled within get_event_selection if possible
            return

        # Show confirmation dialog using the obtained message
        view = ConfirmDeleteView()
        try:
            await message.edit(  # Edit the message from the dropdown
                content=f"⚠️ Are you sure you want to delete the event '{event.details.name}'?",
                view=view,
                embed=None,
            )
        except (discord.NotFound, discord.HTTPException) as e:
            self.logger.warning(f"Failed to edit message for delete confirmation: {e}")
            return  # Can't proceed if message is gone

        await view.wait()
        if view.value is None:  # Timed out
            with suppress(discord.NotFound, discord.HTTPException):
                await message.edit(
                    content="Event deletion timed out.",
                    view=None,
                    embed=None,
                )
            return

        if view.value:  # Confirmed delete
            # Remove event from guild's events list
            try:
                guild = Database.get_document(Guild, interaction.guild_id)
                if guild and hasattr(guild, "events") and event._id in guild.events:
                    guild.events.remove(event._id)
                    Database.update_document(guild, {"events": guild.events})
                    self.logger.info(f"Removed event {event._id} from guild {interaction.guild_id}")
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
            delete_error = None
            try:
                Database.delete_document(event)
                self.logger.info(f"Event {event._id} '{event.details.name}' deleted")
            except Exception as e:
                self.logger.error(f"Error deleting event {event._id}: {e}")
                delete_error = e

            # Edit message based on delete result
            try:
                if delete_error:
                    await message.edit(
                        content=f"Error deleting event '{event.details.name}': {delete_error}",
                        view=None,
                        embed=None,
                    )
                else:
                    await message.edit(
                        content=f"Event '{event.details.name}' has been deleted.",
                        view=None,
                        embed=None,  # Ensure embed is cleared
                    )
            except (discord.NotFound, discord.HTTPException) as e:
                self.logger.warning(f"Failed to edit message after event deletion: {e}")

        else:  # Cancelled delete
            try:
                await message.edit(
                    content="Event deletion cancelled.",
                    view=None,
                    embed=None,  # Ensure embed is cleared
                )
            except (discord.NotFound, discord.HTTPException) as e:
                self.logger.warning(f"Failed to edit message after event deletion cancelled: {e}")

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

        # Create the embed
        embed = discord.Embed(
            title=event.details.name,
            description=event.details.description,
            color=discord.Color.purple(),
        )

        # Add event details
        localized_time = self.format_datetime(event.details.time)
        embed.add_field(name="Date/Time", value=localized_time, inline=True)
        embed.add_field(name="Location", value=event.details.location, inline=True)

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
        else:
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

        if isinstance(channel, (discord.TextChannel | discord.Thread)):
            with suppress(discord.NotFound, discord.Forbidden):
                message = await channel.fetch_message(payload.message_id)
        else:
            return  # Or log unsupported channel type

        try:
            # Use MongoEngine directly for a query by message_id
            event = Event.objects(message_id=payload.message_id).first()
            if not event:
                return
        except Exception as e:
            self.logger.error(f"Error finding event by message_id {payload.message_id}: {e}")
            return

        # Handle different reactions
        emoji = str(payload.emoji)
        user = self.bot.get_user(payload.user_id)

        # Remove any other reactions from this user on this message
        for reaction in message.reactions:
            if str(reaction.emoji) != emoji and user:
                with suppress(discord.NotFound, discord.HTTPException):
                    await reaction.remove(user)

        # Update event attendance based on reaction
        if emoji == "✅":
            await self.handle_attendance_add(payload.user_id, event)
        elif emoji == "❌":
            await self.handle_attendance_remove(payload.user_id, event)
        elif emoji == "❔":
            await self.handle_attendance_maybe(payload.user_id, event)

    async def handle_attendance_add(self, user_id: int, event: Event) -> None:
        """Handle adding a user to event attendance with "yes" response."""
        user = Database.get_document(User, user_id)

        if not user:
            self.logger.info(f"User {user_id} not registered; ignoring attendance add.")
            return

        # Create a copy of the event to modify
        modified = False

        # First, check if the user is in any of the other lists and remove them
        # Remove from maybe_users if present
        if user_id in event.maybe_users:
            event.maybe_users.remove(user_id)
            if event.details and event.details.reactions:
                event.details.reactions.maybe = max(0, event.details.reactions.maybe - 1)
            modified = True

        # Remove from no_users if present
        if user_id in event.no_users:
            event.no_users.remove(user_id)
            if event.details and event.details.reactions:
                event.details.reactions.no = max(0, event.details.reactions.no - 1)
            modified = True

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
            event = Event.objects(message_id=payload.message_id).first()
            if not event:
                return
        except Exception as e:
            self.logger.error(f"Error finding event by message_id {payload.message_id}: {e}")
            return

        # Handle different reactions being removed
        emoji = str(payload.emoji)
        user_id = payload.user_id
        modified = False

        # Process the removal of reaction based on which emoji was removed
        if emoji == "✅" and user_id in event.yes_users:
            # Remove from yes list
            event.yes_users.remove(user_id)
            if event.details and event.details.reactions:
                event.details.reactions.yes = max(0, event.details.reactions.yes - 1)
            modified = True

            # Remove event from user's list
            user = Database.get_document(User, user_id)
            if user and hasattr(user, "events") and event._id in user.events:
                user.events.remove(event._id)
                user.save()
                self.logger.info(
                    f"Removed event {event._id} "
                    f"from user {user_id}'s event list after reaction removal."
                )

        elif emoji == "❌" and user_id in event.no_users:
            # Remove from no list
            event.no_users.remove(user_id)
            if event.details and event.details.reactions:
                event.details.reactions.no = max(0, event.details.reactions.no - 1)
            modified = True

        elif emoji == "❔" and user_id in event.maybe_users:
            # Remove from maybe list
            event.maybe_users.remove(user_id)
            if event.details and event.details.reactions:
                event.details.reactions.maybe = max(0, event.details.reactions.maybe - 1)
            modified = True

            # Remove event from user's list
            user = Database.get_document(User, user_id)
            if user and hasattr(user, "events") and event._id in user.events:
                user.events.remove(event._id)
                user.save()
                self.logger.info(
                    f"Removed event {event._id}"
                    f"from user {user_id}'s event list after maybe reaction removal."
                )

        # Save the event document if modified
        if modified:
            event.save()
            self.logger.info(
                f"Updated event {event._id} for user {user_id} after reaction removal."
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

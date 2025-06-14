"""Event management cog for handling events."""

import logging
import re
from typing import Union, Dict, Optional, Any, cast
from datetime import datetime, timezone
import pytz
import asyncio

import discord
from discord import app_commands
from discord.ext import commands

from config import settings
from backend.db.database import Database as db
from backend.db.documents.user import User
from backend.db.documents.guild import Guild
from backend.db.documents.event import Event, EventDetails, EventReactions
from frontend.interactions.bases.button_base import ConfirmDeleteView
from frontend.interactions.bases.modal_base import DynamicModalView
from frontend.interactions.bases.dropdown_base import DynamicDropdownView
from frontend.interactions.bases.button_base import ConfirmView

from .event_config import EVENT_CONFIG


class EventCog(commands.Cog):
    """Event management cog for handling guild events."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.logger = logging.getLogger(
            f"discord.cog.{self.__class__.__name__.lower()}"
        )
        self.allowed_reactions = ["✅", "❌", "❔"]
        self.config = EVENT_CONFIG
        self.logger.info("Event cog initialized.")

    def now(self) -> datetime:
        """Returns current time in UTC."""
        return datetime.now(timezone.utc)

    def parse_datetime(
        self, date_str: str, time_str: str, timezone_str: Optional[str] = None
    ) -> datetime:
        """Parse date and time strings into a datetime object."""
        try:
            # Extract timezone from time string if not provided separately
            if timezone_str is None:
                time_parts_check = time_str.split()
                if len(time_parts_check) > 2:
                    timezone_str = time_parts_check[-1]
                    time_str = " ".join(time_parts_check[:-1])
            # Default to Eastern Time if no timezone is specified
            if timezone_str is None:
                timezone_str = "US/Eastern"

            # Parse the date (expected format: MM/DD/YY)
            month, day, year = map(int, date_str.split("/"))
            year = (
                2000 + year if year < 100 else year
            )  # Convert 2-digit year to 4-digit

            # Parse the time (expected format: HH:MM AM/PM)
            time_parts = time_str.strip().split()
            hour, minute = map(int, time_parts[0].split(":"))

            # Adjust for AM/PM
            if time_parts[1].upper() == "PM" and hour < 12:
                hour += 12
            elif time_parts[1].upper() == "AM" and hour == 12:
                hour = 0

            # Create datetime object
            dt = datetime(year, month, day, hour, minute)

            # Set the timezone
            tz = pytz.timezone(timezone_str)
            dt = tz.localize(dt) if dt.tzinfo is None else dt.astimezone(tz)

            return dt
        except Exception as e:
            self.logger.error(f"Error parsing date/time: {e}")
            raise ValueError(f"Invalid date/time format: {date_str} {time_str}")

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

    def _validate_event_form(self, form_data: Dict[str, str]) -> bool:
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
        if not re.match(
            r"^(0?[1-9]|1[0-2]):([0-5][0-9])\s+(AM|PM)(\s+[A-Z]{2,4})?$",
            time_str,
            re.IGNORECASE,
        ):
            return False

        return True

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
            # This ensures we always respond to the interaction before it expires
            guild = db.get_document(Guild, interaction.guild_id)
            if not guild or not hasattr(guild, "events") or not guild.events:
                # No events exist, so respond immediately
                await interaction.response.send_message(
                    "No events found for this server.", ephemeral=True
                )
                return

            # Check if there are any events that can be deleted
            has_events = False
            for event_id in guild.events:
                event = db.get_document(Event, event_id)
                if event and hasattr(event, "details"):
                    has_events = True
                    break

            if not has_events:
                await interaction.response.send_message(
                    "No events found for this server.", ephemeral=True
                )
                return

            # Continue with event deletion since events exist
            await self.delete_event_selection(interaction)
        elif action == "announce":
            await self.announce_event_selection(interaction)
        elif action == "myevents":
            await self.my_events(interaction)

    async def create_event(self, interaction: discord.Interaction) -> None:
        """Handle event creation."""
        self.logger.info(f"Event creation requested by {interaction.user}")

        try:
            # Get event data from modal
            self.logger.info("Creating modal view")
            modal_view = DynamicModalView(**self.config["event_modal"])
            self.logger.info("Initiating modal interaction")
            event_data, modal_message = await modal_view.initiate_from_interaction(
                interaction
            )

            self.logger.info(
                f"Modal result: data={event_data is not None}, message exists={modal_message is not None}"
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

            # Prepare the timezone dropdown configuration.
            # Remove invalid keys and convert "options" to "selections"
            timezone_config = self.config["timezone_dropdown"].copy()
            timezone_config.pop("placeholder", None)

            dropdowns = timezone_config.get("dropdowns", [])
            if isinstance(dropdowns, list):
                for dropdown in dropdowns:
                    if isinstance(dropdown, dict) and "options" in dropdown:
                        dropdown["selections"] = dropdown.pop("options")
                timezone_config["dropdowns"] = (
                    dropdowns  # reassign in case anything was changed
                )

            # Get timezone selection with dropdown
            self.logger.info("Creating timezone dropdown")
            timezone_view = DynamicDropdownView(**timezone_config)
            timezone_data, dropdown_message = await timezone_view.initiate_from_message(
                modal_message, "Please select a timezone for the event:"
            )

            # If no timezone selection is returned, try to get the default from configuration
            if not timezone_data or not timezone_data.get("timezone_selection"):
                self.logger.info(
                    "No timezone data received, attempting to use default from config"
                )
                default_timezone = None

                # Cast dropdowns for typing help
                fallback_dropdowns = cast(
                    list[dict[str, Any]],
                    self.config["timezone_dropdown"].get("dropdowns", []),
                )

                for dropdown in fallback_dropdowns:
                    options = dropdown.get("options", [])
                    if isinstance(options, list):
                        for option in options:
                            if isinstance(option, dict) and option.get("default"):
                                default_timezone = option.get("value")
                                break
                    if default_timezone:
                        break

                if not default_timezone:
                    default_timezone = "US/Eastern"

                timezone_data = {"timezone_selection": [default_timezone]}

            # Get timezone or use default
            timezone = timezone_data.get("timezone_selection", ["US/Eastern"])[0]

            # Convert timezone string to a pytz timezone object
            tz = pytz.timezone(timezone)

            # Parse the date and time into a datetime object
            event_time = self.parse_datetime(
                event_data["event_date"], event_data["event_time"], timezone
            )

            # Create a unique event ID using the provided timezone
            event_id = int(datetime.now(tz).timestamp() * 1000)

            new_event = Event(
                _id=event_id,
                guild_id=interaction.guild_id,
                yes_users=[],
                maybe_users=[],
                no_users=[],
                message_id=0,  # Will be updated if/when announced
                details=EventDetails(
                    name=event_data["event_name"],
                    description=event_data["event_description"],
                    time=event_time,
                    location=event_data["event_location"],
                    reactions=EventReactions(yes=0, no=0, maybe=0),
                ),
            )

            # Save the event to the database
            db.add_document(new_event)
            self.logger.info(f"Event saved to database with ID {event_id}")

            # Update the guild document to include this event
            guild = db.get_document(Guild, interaction.guild_id)
            if not guild:
                guild = Guild(_id=interaction.guild_id, events=[])
                db.add_document(guild)
            elif not hasattr(guild, "events"):
                guild.events = []

            guild.events.append(event_id)
            db.update_document(guild, {"events": guild.events})
            self.logger.info(f"Guild document updated with event ID {event_id}")

            # Show the event details
            await self.show_event_embed(dropdown_message, new_event)
            self.logger.info(
                f"Event '{event_data['event_name']}' created with ID {event_id}"
            )

        except Exception as e:
            self.logger.error(f"Exception in create_event: {e}", exc_info=True)
            if interaction.response.is_done():
                await interaction.followup.send(
                    f"Error creating event: {str(e)}", ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"Error creating event: {str(e)}", ephemeral=True
                )

    async def list_events(self, interaction: discord.Interaction) -> None:
        """List all upcoming events for the guild."""
        self.logger.info(f"Listing events for guild {interaction.guild_id}")

        guild = db.get_document(Guild, interaction.guild_id)
        if not guild or not hasattr(guild, "events") or not guild.events:
            self.logger.info(f"No events found for guild {interaction.guild_id}")
            await interaction.followup.send(
                "No events found for this server.", ephemeral=True
            )
            return

        # Get all upcoming events from guild's event list
        current_time = self.now()
        guild_events = []

        self.logger.info(
            f"Found {len(guild.events)} events for guild {interaction.guild_id}"
        )
        for event_id in guild.events:
            event = db.get_document(Event, event_id)
            if event and hasattr(event, "details"):
                event_time = event.details.time
                # If the event time is offset-naive, assume it's in UTC (or use another default timezone)
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
                value=f"**When:** {localized_time}\n**Where:** {event.details.location}\n**Attendees:** {total_attendees}",
                inline=False,
            )

        await interaction.followup.send(embed=embed, ephemeral=True)

    async def get_event_selection(
        self, interaction: discord.Interaction, action: str
    ) -> tuple[Optional[Event], Optional[discord.Message]]:
        """Get event selection from dropdown. Returns (Event, Message) or (None, None)."""
        message: Optional[discord.Message] = None  # Initialize message variable
        try:
            # Get all events for this guild
            guild = db.get_document(Guild, interaction.guild_id)
            if not guild or not hasattr(guild, "events") or not guild.events:
                try:
                    if interaction.response.is_done():
                        await interaction.followup.send(
                            "No events found for this server.", ephemeral=True
                        )
                    else:
                        await interaction.response.send_message(
                            "No events found for this server.", ephemeral=True
                        )

                except (discord.NotFound, discord.HTTPException) as e:
                    self.logger.warning(f"Could not send 'no events' message: {e}")
                return None, None  # Return None for both event and message

            # Get all upcoming events (or all for delete)
            current_time = self.now()
            guild_events = []

            for event_id in guild.events:
                event = db.get_document(Event, event_id)
                if event and hasattr(event, "details"):
                    event_time = event.details.time
                    if event_time.tzinfo is None:
                        event_time = pytz.UTC.localize(event_time)
                    if action == "delete" or event_time >= current_time:
                        guild_events.append(event)

            if not guild_events:
                try:
                    if interaction.response.is_done():
                        await interaction.followup.send(
                            "No matching events found.", ephemeral=True
                        )
                    else:
                        await interaction.response.send_message(
                            "No matching events found.", ephemeral=True
                        )

                except (discord.NotFound, discord.HTTPException) as e:
                    self.logger.warning(
                        f"Could not send 'no matching events' message: {e}"
                    )
                return None, None  # Return None for both event and message

            # Create dropdown options
            options = []
            for event in guild_events:
                options.append(
                    {
                        "label": f"{event.details.name}",
                        "description": self.format_datetime(event.details.time)[
                            :99
                        ],  # Ensure description fits
                        "value": str(event._id),
                    }
                )

            # Create dropdown config
            dropdown_config = {
                "ephemeral": True,
                "add_buttons": True,
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

            # Create dropdown view
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
                    await view.wait()  # Wait for the view interaction
                    # Get selected values after waiting
                    selections = {}
                    for dropdown in view._dropdowns:
                        if dropdown.selected_values:
                            selections[dropdown.custom_id] = dropdown.selected_values
                    values = selections if view.accepted else None

                else:
                    # Use initiate_from_interaction if the response hasn't been sent
                    # This sends the initial response message
                    values, message = await view.initiate_from_interaction(
                        interaction, f"Please select an event to {action}:"
                    )
            except (discord.NotFound, discord.HTTPException) as e:
                self.logger.warning(
                    f"Interaction/HTTP error during event selection for {action}: {e}"
                )
                # Cannot edit message if interaction expired, return None, None
                return None, None
            except Exception as e:
                self.logger.error(
                    f"Unexpected error during dropdown view handling: {e}",
                    exc_info=True,
                )
                # Ensure we return two Nones
                return None, None

            # --- Process the selection ---
            if not view.accepted or not values or not message:
                # User cancelled, timed out, or interaction failed
                if message and not view.is_finished():  # Check if view finished itself
                    try:
                        await message.edit(
                            content="Event selection cancelled or timed out.",
                            view=None,
                            embed=None,
                        )
                    except (discord.NotFound, discord.HTTPException):
                        pass  # Ignore if message is already gone
                return None, None  # Return None for both

            # Get the selected event ID string
            selected_id_str = values.get("event_selection", [None])[0]
            if not selected_id_str:
                # Should not happen if view.accepted is True, but check anyway
                return None, None  # Return None for both

            # Convert ID to int
            try:
                selected_id = int(selected_id_str)
            except ValueError:
                self.logger.error(f"Invalid event ID selected: {selected_id_str}")
                # Try to edit the message to show error
                try:
                    await message.edit(
                        content=f"Error: Invalid event ID selected ({selected_id_str}).",
                        view=None,
                        embed=None,
                    )
                except (discord.NotFound, discord.HTTPException):
                    pass
                return None, None  # Return None for both

            # Fetch the event document
            selected_event = db.get_document(Event, selected_id)
            if not selected_event:
                # Event ID was valid int but not found in DB (maybe deleted?)
                self.logger.warning(
                    f"Selected event ID {selected_id} not found in database."
                )
                try:
                    await message.edit(
                        content=f"Error: Event with ID {selected_id} not found.",
                        view=None,
                        embed=None,
                    )
                except (discord.NotFound, discord.HTTPException):
                    pass
                return None, message  # Return None for event, but keep message context

            # Success: Return the event document and the message
            return selected_event, message

        except Exception as e:
            self.logger.error(
                f"Outer error in get_event_selection: {str(e)}", exc_info=True
            )
            # Ensure we return two values even on unexpected error
            # Try to inform user if possible
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(
                        "An unexpected error occurred while selecting the event.",
                        ephemeral=True,
                    )
                else:
                    await interaction.response.send_message(
                        "An unexpected error occurred while selecting the event.",
                        ephemeral=True,
                    )

            except (discord.NotFound, discord.HTTPException):
                pass  # Best effort
            return None, None  # Return None for both

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
        # Original interaction is the command. It's not deferred by the main /event handler for "edit".
        self.logger.info(f"Event edit process started by {interaction.user.id}")

        # 1. Get Event to Edit
        selected_event, event_selection_message = await self.get_event_selection(
            interaction, "edit"
        )

        if not selected_event:
            self.logger.info("Event selection for edit failed or was cancelled.")
            if not event_selection_message and not interaction.response.is_done():
                try:
                    await interaction.response.send_message(
                        "Failed to select an event for editing.", ephemeral=True
                    )
                except discord.HTTPException:
                    self.logger.warning(
                        "Failed to send fallback message for event selection failure."
                    )
            return

        if not event_selection_message:
            self.logger.error(
                "get_event_selection returned an event but no message. Aborting edit."
            )
            try:
                await interaction.followup.send(
                    "An internal error occurred while selecting the event for editing. Please try again.",
                    ephemeral=True,
                )
            except discord.HTTPException:
                self.logger.warning(
                    "Failed to send followup for internal error in event selection message."
                )
            return

        self.logger.info(
            f"Event {selected_event._id} ('{selected_event.details.name}') selected for editing."
        )

        # 2. Attribute Selection Dropdown
        current_event_time = selected_event.details.time
        attribute_map = {
            "name": {"label": "Name", "current_val": selected_event.details.name},
            "description": {
                "label": "Description",
                "current_val": selected_event.details.description,
            },
            "location": {
                "label": "Location",
                "current_val": selected_event.details.location,
            },
            "date": {
                "label": "Date (MM/DD/YY)",
                "current_val": current_event_time.strftime("%m/%d/%y"),
            },
            "time": {
                "label": "Time (HH:MM AM/PM)",
                "current_val": current_event_time.strftime("%I:%M %p"),
            },
            "timezone": {
                "label": "Timezone",
                "current_val": str(current_event_time.tzinfo),
            },
        }
        dropdown_options = [
            {"label": data["label"], "value": key}
            for key, data in attribute_map.items()
        ]

        attribute_dropdown_config = {
            "ephemeral": True,
            "add_buttons": True,
            "timeout": 180.0,
            "dropdowns": [
                {
                    "custom_id": "attribute_to_edit",
                    "placeholder": "Select an attribute to edit",
                    "min_values": 1,
                    "max_values": 1,
                    "selections": dropdown_options,
                }
            ],
        }
        attribute_view = DynamicDropdownView(**attribute_dropdown_config)

        self.logger.debug(
            f"Presenting attribute selection dropdown for event {selected_event._id}"
        )
        selected_attribute_data, attribute_selection_message_edited = (
            await attribute_view.initiate_from_message(
                event_selection_message,
                content=f"Editing event: **{selected_event.details.name}**\nSelect an attribute to change:",
            )
        )

        if not attribute_selection_message_edited:
            self.logger.error(
                "Attribute selection dropdown failed to produce a message after editing."
            )
            try:
                await interaction.followup.send(
                    "An error occurred displaying attribute choices. Please try again.",
                    ephemeral=True,
                )
            except discord.HTTPException:
                self.logger.warning(
                    "Failed to send followup for attribute dropdown message failure."
                )
            return

        current_message_being_edited = attribute_selection_message_edited

        if not selected_attribute_data or not attribute_view.accepted:
            self.logger.info("Attribute selection cancelled or timed out.")
            await current_message_being_edited.edit(
                content="Event editing cancelled: No attribute selected or selection cancelled.",
                view=None,
                embed=None,
            )
            return

        selected_attribute_key = selected_attribute_data.get("attribute_to_edit")[0]
        attr_info = attribute_map[selected_attribute_key]
        self.logger.info(
            f"Attribute '{selected_attribute_key}' selected for editing event {selected_event._id}."
        )

        # 3. Get New Value
        new_value_str = None

        if selected_attribute_key == "timezone":
            prompt_message_content = (
                f"Editing **{attr_info['label']}** for event **{selected_event.details.name}**.\n"
                f"Current value: `{attr_info['current_val']}`\n\n"
                "Please select the new **Timezone** from the dropdown below:"
            )

            # Prepare timezone dropdown options from self.config
            timezone_options_from_config = []
            raw_tz_config_dropdowns = self.config.get("timezone_dropdown", {}).get(
                "dropdowns", []
            )

            if (
                raw_tz_config_dropdowns
                and isinstance(raw_tz_config_dropdowns, list)
                and len(raw_tz_config_dropdowns) > 0
            ):
                # Assuming the first dropdown in the config is the one we want for timezone options
                first_tz_dropdown_config = raw_tz_config_dropdowns[0]
                if isinstance(first_tz_dropdown_config, dict):
                    options_key = (
                        "selections"
                        if "selections" in first_tz_dropdown_config
                        else "options"
                    )
                    timezone_options_from_config = first_tz_dropdown_config.get(
                        options_key, []
                    )

            if (
                not timezone_options_from_config
            ):  # Fallback if config is missing/empty or malformed
                self.logger.warning(
                    "Timezone dropdown config missing or empty for edit. Using fallback options."
                )
                timezone_options_from_config = [
                    {"label": "US/Eastern", "value": "US/Eastern", "default": True},
                    {"label": "US/Central", "value": "US/Central"},
                    {"label": "US/Mountain", "value": "US/Mountain"},
                    {"label": "US/Pacific", "value": "US/Pacific"},
                    {"label": "UTC", "value": "UTC"},
                    {"label": "Europe/London", "value": "Europe/London"},
                ]

            edit_timezone_dropdown_config = {
                "ephemeral": True,  # Keep ephemeral nature of the edit flow
                "add_buttons": True,  # Standard confirm/cancel
                "timeout": 120.0,
                "dropdowns": [
                    {
                        "custom_id": "edit_event_new_timezone",  # Unique custom_id for this context
                        "placeholder": "Select new timezone",
                        "min_values": 1,
                        "max_values": 1,
                        "selections": timezone_options_from_config,  # Use options from config or fallback
                    }
                ],
            }
            timezone_edit_view = DynamicDropdownView(**edit_timezone_dropdown_config)

            # Edit the message that was previously showing the text prompt, now to show this dropdown
            selected_tz_data, final_message_after_tz_dropdown = (
                await timezone_edit_view.initiate_from_message(
                    current_message_being_edited,  # This is the message to edit
                    content=prompt_message_content,
                )
            )

            # Update current_message_being_edited to the latest version if it was changed by initiate_from_message
            if final_message_after_tz_dropdown:
                current_message_being_edited = final_message_after_tz_dropdown

            if not timezone_edit_view.accepted or not selected_tz_data:
                self.logger.info(
                    f"Timezone selection timed out or cancelled for event edit (event ID: {selected_event._id})."
                )
                # Ensure the message reflects cancellation if it's still editable
                try:
                    await current_message_being_edited.edit(
                        content="Event editing timed out or cancelled: No new timezone selected.",
                        view=None,
                        embed=None,
                    )
                except (discord.NotFound, discord.HTTPException):
                    pass  # Message might be gone
                return

            new_value_str = selected_tz_data.get("edit_event_new_timezone", [None])[0]
            # The message `current_message_being_edited` will be further edited by success/failure/embed logic later.

        else:
            # --- Existing direct message reply logic for other attributes ---
            prompt_message_content = (
                f"Editing **{attr_info['label']}** for event **{selected_event.details.name}**.\n"
                f"Current value: `{attr_info['current_val']}`\n\n"
            )
            if selected_attribute_key == "date":
                prompt_message_content += "Please type the new **Date** in `MM/DD/YY` format (e.g., `07/04/25`):"
            elif selected_attribute_key == "time":
                prompt_message_content += "Please type the new **Time** in `HH:MM AM/PM` format (e.g., `03:30 PM`):"
            # No 'timezone' here anymore as it's handled above
            else:  # For name, description, location
                prompt_message_content += f"Please type the new value for **{attr_info['label']}** in the chat and press Enter:"

            await current_message_being_edited.edit(
                content=prompt_message_content, view=None, embed=None
            )  # Ensure view is cleared

            try:
                reply_message = await self.bot.wait_for(
                    "message",
                    check=lambda m: m.author.id == interaction.user.id
                    and m.channel.id == current_message_being_edited.channel.id,
                    timeout=180.0,
                )
                new_value_str = reply_message.content.strip()
                try:
                    await reply_message.delete()
                except discord.HTTPException:
                    self.logger.warning(
                        f"Failed to delete user's reply message (ID: {reply_message.id}) for event edit."
                    )
            except asyncio.TimeoutError:
                self.logger.info(
                    f"User input timed out for event edit (event ID: {selected_event._id})."
                )
                await current_message_being_edited.edit(
                    content="Event editing timed out: No new value provided.",
                    view=None,
                    embed=None,
                )
                return
            except Exception as e:
                self.logger.error(
                    f"Error waiting for or processing reply for event edit (event ID: {selected_event._id}): {e}",
                    exc_info=True,
                )
                await current_message_being_edited.edit(
                    content="An error occurred while getting your input. Please try again.",
                    view=None,
                    embed=None,
                )
                return

        if not new_value_str:
            self.logger.info(
                f"User provided/selected empty value for event edit (event ID: {selected_event._id})."
            )
            await current_message_being_edited.edit(
                content="Event editing cancelled: No new value provided/selected.",
                view=None,
                embed=None,
            )
            return

        # 4. Validate and Update Event
        try:
            original_event_name_for_confirmation = selected_event.details.name
            current_dt = selected_event.details.time

            if selected_attribute_key == "name":
                if not new_value_str:
                    raise ValueError("Name cannot be empty.")
                selected_event.details.name = new_value_str
            elif selected_attribute_key == "description":
                if not new_value_str:
                    raise ValueError("Description cannot be empty.")
                selected_event.details.description = new_value_str
            elif selected_attribute_key == "location":
                if not new_value_str:
                    raise ValueError("Location cannot be empty.")
                selected_event.details.location = new_value_str
            elif selected_attribute_key == "date":
                date_regex = r"^(0[1-9]|1[0-2])/(0[1-9]|[12][0-9]|3[01])/\d{2}$"
                if not re.match(date_regex, new_value_str):
                    raise ValueError(
                        "Invalid Date format. Please use `MM/DD/YY` (e.g., `07/04/25`)."
                    )
                time_part = current_dt.strftime("%I:%M %p")
                tz_part = str(current_dt.tzinfo)
                selected_event.details.time = self.parse_datetime(
                    new_value_str, time_part, tz_part
                )
            elif selected_attribute_key == "time":
                time_regex = r"^(0?[1-9]|1[0-2]):([0-5][0-9])\s+(AM|PM)$"
                if not re.match(time_regex, new_value_str, re.IGNORECASE):
                    raise ValueError(
                        "Invalid Time format. Please use `HH:MM AM/PM` (e.g., `03:30 PM`)."
                    )
                date_part = current_dt.strftime("%m/%d/%y")
                tz_part = str(current_dt.tzinfo)
                selected_event.details.time = self.parse_datetime(
                    date_part, new_value_str, tz_part
                )
            elif selected_attribute_key == "timezone":
                try:
                    new_tz = pytz.timezone(new_value_str)
                    selected_event.details.time = current_dt.astimezone(new_tz)
                except pytz.exceptions.UnknownTimeZoneError:
                    raise ValueError(
                        f"Invalid timezone: '{new_value_str}'. Please use a valid Olson timezone name (e.g., US/Eastern, UTC, Europe/London)."
                    )
                except Exception as e_tz:
                    self.logger.error(
                        f"Error processing timezone '{new_value_str}': {e_tz}"
                    )
                    raise ValueError(
                        f"Could not process timezone: {new_value_str}. Please ensure it's a valid format."
                    )

            selected_event.save()
            self.logger.info(
                f"Event '{original_event_name_for_confirmation}' (ID: {selected_event._id}) updated. Attribute: {selected_attribute_key}."
            )

            # 5. Show Updated Embed
            await self.show_event_embed(current_message_being_edited, selected_event)

            await interaction.followup.send(
                f"Event **{selected_event.details.name}** has been updated successfully!",
                ephemeral=True,
            )
            self.logger.info(
                f"Successfully updated and displayed event {selected_event._id}"
            )

        except ValueError as e:
            self.logger.warning(
                f"Validation error during event edit (event ID: {selected_event._id}): {e}"
            )
            await current_message_being_edited.edit(
                content=f"Invalid input: {e}\nPlease try editing the event again.",
                view=None,
                embed=None,
            )
        except Exception as e:
            self.logger.error(
                f"Error updating event {selected_event._id} in database: {e}",
                exc_info=True,
            )
            await current_message_being_edited.edit(
                content="An error occurred while updating the event in the database. Please try again.",
                view=None,
                embed=None,
            )
            try:
                await interaction.followup.send(
                    "An error occurred while saving your event changes. Please try again.",
                    ephemeral=True,
                )
            except discord.HTTPException:
                pass

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
        try:
            if view.value:  # Confirmed delete
                # ... (rest of your deletion logic) ...

                await message.edit(
                    content=f"Event '{event.details.name}' has been deleted.",
                    view=None,
                    embed=None,  # Ensure embed is cleared
                )
            else:  # Cancelled delete
                await message.edit(
                    content="Event deletion cancelled.",
                    view=None,
                    embed=None,  # Ensure embed is cleared
                )
        except (discord.NotFound, discord.HTTPException) as e:
            self.logger.warning(
                f"Failed to edit message after delete confirmation: {e}"
            )
            # Log deletion status if possible
            if view.value:
                self.logger.info(
                    f"Event {event._id} was deleted, but confirmation message failed."
                )
            else:
                self.logger.info(
                    f"Event {event._id} deletion was cancelled, but cancellation message failed."
                )

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
                content=f"Are you sure you want to announce the event '{event.details.name}' in the announcements channel?",
                view=view,
                embed=None,
            )
        except (discord.NotFound, discord.HTTPException) as e:
            self.logger.warning(
                f"Failed to edit message for announce confirmation: {e}"
            )
            return  # Can't proceed if message is gone

        await view.wait()

        # Check if announcement was cancelled early
        if not view.value:
            try:
                await message.edit(
                    content="Event announcement cancelled.",
                    view=None,
                    embed=None,  # Clear embed
                )
            except (discord.NotFound, discord.HTTPException):
                pass  # Best effort
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
            try:
                await message.edit(
                    content="Error: Could not find or create the announcements channel.",
                    view=None,
                    embed=None,
                )
            except (discord.NotFound, discord.HTTPException):
                pass
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
            db.update_document(event, {"message_id": announcement.id})

            # Update the original confirmation message
            await message.edit(
                content=f"Event announced in #{announcement_channel.name}!",
                view=None,
                embed=None,  # Clear embed
            )
        except discord.Forbidden:
            self.logger.error(
                f"Permission error announcing event {event._id} in channel {announcement_channel.id}"
            )
            try:
                await message.edit(
                    content="Error: I don't have permission to send messages or add reactions in the announcements channel.",
                    view=None,
                    embed=None,  # Clear embed
                )
            except (discord.NotFound, discord.HTTPException):
                pass
        except Exception as e:
            self.logger.error(
                f"Error during event announcement send/react: {e}", exc_info=True
            )
            try:
                await message.edit(
                    content="An error occurred while sending the announcement.",
                    view=None,
                    embed=None,  # Clear embed
                )
            except (discord.NotFound, discord.HTTPException):
                pass

    async def my_events(self, interaction: discord.Interaction) -> None:
        """Show events the user is registered for with registration status."""
        user = db.get_document(User, interaction.user.id)
        if not user or not hasattr(user, "events") or not user.events:
            await interaction.followup.send(
                "You're not registered for any events.", ephemeral=True
            )
            return

        # Get all events the user is registered for
        user_events = []
        current_time = self.now()

        for event_id in user.events:
            event = db.get_document(Event, event_id)
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
                value=f"**When:** {localized_time}\n**Where:** {event.details.location}\n**Your Status:** {status}",
                inline=False,
            )

        await interaction.followup.send(embed=embed, ephemeral=True)

    async def show_event_embed(
        self,
        message_or_interaction: Union[discord.Message, discord.Interaction],
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

        if isinstance(channel, (discord.TextChannel, discord.Thread)):
            try:
                message = await channel.fetch_message(payload.message_id)
            except (discord.NotFound, discord.Forbidden):
                return
        else:
            return  # Or log unsupported channel type

        try:
            # Use MongoEngine directly for a query by message_id
            event = Event.objects(message_id=payload.message_id).first()
            if not event:
                return
        except Exception as e:
            self.logger.error(
                f"Error finding event by message_id {payload.message_id}: {e}"
            )
            return

        # Handle different reactions
        emoji = str(payload.emoji)
        user = self.bot.get_user(payload.user_id)

        # Remove any other reactions from this user on this message
        for reaction in message.reactions:
            if str(reaction.emoji) != emoji and user:
                try:
                    await reaction.remove(user)
                except (discord.Forbidden, discord.NotFound, discord.HTTPException):
                    pass

        # Update event attendance based on reaction
        if emoji == "✅":
            await self.handle_attendance_add(payload.user_id, event)
        elif emoji == "❌":
            await self.handle_attendance_remove(payload.user_id, event)
        elif emoji == "❔":
            await self.handle_attendance_maybe(payload.user_id, event)

    async def handle_attendance_add(self, user_id: int, event: Event) -> None:
        """Handle adding a user to event attendance with "yes" response."""
        user = db.get_document(User, user_id)

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
                event.details.reactions.maybe = max(
                    0, event.details.reactions.maybe - 1
                )
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
            self.logger.info(
                f"Updated event {event._id} for user {user_id} with 'yes' response."
            )

        # Handle user document updates
        if not hasattr(user, "events"):
            user.events = []

        # Ensure event is in user's list
        if event._id not in user.events:
            user.events.append(event._id)
            user.save()
            self.logger.info(
                f"Updated user {user_id} for event {event._id} with 'yes' response."
            )

    async def handle_attendance_remove(self, user_id: int, event: Event) -> None:
        """Handle marking a user with "no" response (not attending)."""
        user = db.get_document(User, user_id)

        if not user:
            self.logger.info(
                f"User {user_id} not registered; ignoring attendance removal."
            )
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
                event.details.reactions.maybe = max(
                    0, event.details.reactions.maybe - 1
                )
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
            self.logger.info(
                f"Updated event {event._id} for user {user_id} with 'no' response."
            )

        # Handle user document updates - a "no" response means removing the event from the user's list
        if hasattr(user, "events") and event._id in user.events:
            user.events.remove(event._id)
            user.save()
            self.logger.info(
                f"Removed event {event._id} from user {user_id}'s event list."
            )

    async def handle_attendance_maybe(self, user_id: int, event: Event) -> None:
        """Handle marking a user as maybe for event attendance."""
        user = db.get_document(User, user_id)

        if not user:
            self.logger.info(
                f"User {user_id} not registered; ignoring maybe attendance."
            )
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
            self.logger.info(
                f"Updated event {event._id} for user {user_id} with 'maybe' response."
            )

        # Add event to user list if they fill maybe
        if event._id not in user.events:
            user.events.append(event._id)
            user.save()
            self.logger.info(
                f"Updated user {user_id} for event {event._id} with 'maybe' response."
            )

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
            # Find the event by message ID
            event = Event.objects(message_id=payload.message_id).first()
            if not event:
                return
        except Exception as e:
            self.logger.error(
                f"Error finding event by message_id {payload.message_id}: {e}"
            )
            return

        # Handle different reactions being removed
        emoji = str(payload.emoji)
        user_id = payload.user_id
        modified = False

        # Process the removal of reaction based on which emoji was removed
        if emoji == "✅":
            # Remove from yes list
            if user_id in event.yes_users:
                event.yes_users.remove(user_id)
                if event.details and event.details.reactions:
                    event.details.reactions.yes = max(
                        0, event.details.reactions.yes - 1
                    )
                modified = True

                # Remove event from user's list
                user = db.get_document(User, user_id)
                if user and hasattr(user, "events") and event._id in user.events:
                    user.events.remove(event._id)
                    user.save()
                    self.logger.info(
                        f"Removed event {event._id} from user {user_id}'s event list after reaction removal."
                    )

        elif emoji == "❌":
            # Remove from no list
            if user_id in event.no_users:
                event.no_users.remove(user_id)
                if event.details and event.details.reactions:
                    event.details.reactions.no = max(0, event.details.reactions.no - 1)
                modified = True

        elif emoji == "❔":
            # Remove from maybe list
            if user_id in event.maybe_users:
                event.maybe_users.remove(user_id)
                if event.details and event.details.reactions:
                    event.details.reactions.maybe = max(
                        0, event.details.reactions.maybe - 1
                    )
                modified = True

                # Remove event from user's list
                user = db.get_document(User, user_id)
                if user and hasattr(user, "events") and event._id in user.events:
                    user.events.remove(event._id)
                    user.save()
                    self.logger.info(
                        f"Removed event {event._id} from user {user_id}'s event list after maybe reaction removal."
                    )

        # Save the event document if modified
        if modified:
            event.save()
            self.logger.info(
                f"Updated event {event._id} for user {user_id} after reaction removal."
            )


async def setup(bot: commands.Bot) -> None:
    """Set up the Event cog."""
    await bot.add_cog(EventCog(bot))

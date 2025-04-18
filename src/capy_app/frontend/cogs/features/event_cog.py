"""Event management cog for handling events."""

import logging
import re
from typing import Union, Dict, Optional
from datetime import datetime, timezone
import pytz

import discord
from discord import app_commands
from discord.ext import commands


from config import settings
from backend.db.database import Database as db
from backend.db.documents.user import User
from backend.db.documents.guild import Guild
from backend.db.documents.event import Event, EventDetails, EventReactions
from frontend.interactions.bases.button_base import ConfirmDeleteView
from frontend.interactions.bases.modal_base import DynamicModalView, ButtonDynamicModalView
from frontend.interactions.bases.dropdown_base import DynamicDropdownView
from frontend.interactions.bases.button_base import ConfirmView


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
        return datetime.now(timezone.utc)

    def parse_datetime(self, date_str: str, time_str: str, timezone_str: Optional[str] = None) -> datetime:
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
            month, day, year = map(int, date_str.split('/'))
            year = 2000 + year if year < 100 else year  # Convert 2-digit year to 4-digit

            # Parse the time (expected format: HH:MM AM/PM)
            time_parts = time_str.strip().split()
            hour, minute = map(int, time_parts[0].split(':'))

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
        required_fields = ['event_name', 'event_date', 'event_time', 'event_location', 'event_description']
        for field in required_fields:
            if field not in form_data or not form_data[field].strip():
                return False

        # Validate date format (MM/DD/YY)
        date_str = form_data.get('event_date', '')
        if not re.match(r'^(0[1-9]|1[0-2])/(0[1-9]|[12][0-9]|3[01])/\d{2}$', date_str):
            return False

        # Validate time format (HH:MM AM/PM)
        time_str = form_data.get('event_time', '')
        if not re.match(r'^(0?[1-9]|1[0-2]):([0-5][0-9])\s+(AM|PM)(\s+[A-Z]{2,4})?$', time_str, re.IGNORECASE):
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
            app_commands.Choice(name="delete", value="delete"),
            app_commands.Choice(name="announce", value="announce"),
            app_commands.Choice(name="myevents", value="myevents"),
            app_commands.Choice(name="edit", value="edit"),  # Add the edit option
        ]
    )
    async def event(self, interaction: discord.Interaction, action: str) -> None:
        """Handle event actions."""
        should_defer = action in ["list", "show", "announce", "myevents", "edit"]  # Add edit to defer list
        is_ephemeral = action in ["list", "show", "delete", "announce", "myevents", "edit"]  # Add edit to ephemeral list

        if should_defer:
            await interaction.response.defer(ephemeral=is_ephemeral)

        if action == "create":
            await self.create_event(interaction)
        elif action == "list":
            await self.list_events(interaction)
        elif action == "show":
            await self.show_event_selection(interaction)
        elif action == "delete":
            # This ensures we always respond to the interaction before it expires
            guild = db.get_document(Guild, interaction.guild_id)
            if not guild or not hasattr(guild, 'events') or not guild.events:
                # No events exist, so respond immediately
                await interaction.response.send_message("No events found for this server.", ephemeral=True)
                return

            # Check if there are any events that can be deleted
            has_events = False
            for event_id in guild.events:
                event = db.get_document(Event, event_id)
                if event and hasattr(event, 'details'):
                    has_events = True
                    break

            if not has_events:
                await interaction.response.send_message("No events found for this server.", ephemeral=True)
                return

            # Continue with event deletion since events exist
            await self.delete_event_selection(interaction)
        elif action == "announce":
            await self.announce_event_selection(interaction)
        elif action == "myevents":
            await self.my_events(interaction)
        elif action == "edit":
            await self.edit_event_selection(interaction)  # Add handling for edit action

    async def create_event(self, interaction: discord.Interaction) -> None:
        """Handle event creation."""
        self.logger.info(f"Event creation requested by {interaction.user}")

        try:
            # Get event data from modal
            self.logger.info("Creating modal view")
            modal_view = DynamicModalView(**self.config["event_modal"])
            self.logger.info("Initiating modal interaction")
            event_data, modal_message = await modal_view.initiate_from_interaction(interaction)

            self.logger.info(f"Modal result: data={event_data is not None}, message exists={modal_message is not None}")

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
                    view=None
                )
                return

            self.logger.info("Form data validated successfully")

            # Prepare the timezone dropdown configuration.
            # Remove invalid keys and convert "options" to "selections"
            timezone_config = self.config["timezone_dropdown"].copy()
            timezone_config.pop("placeholder", None)

            if "dropdowns" in timezone_config:
                new_dropdowns = []
                for dropdown in timezone_config["dropdowns"]:
                    if "options" in dropdown:
                        dropdown["selections"] = dropdown.pop("options")
                    new_dropdowns.append(dropdown)
                timezone_config["dropdowns"] = new_dropdowns

            # Get timezone selection with dropdown
            self.logger.info("Creating timezone dropdown")
            timezone_view = DynamicDropdownView(**timezone_config)
            timezone_data, dropdown_message = await timezone_view.initiate_from_message(
                modal_message, "Please select a timezone for the event:"
            )

            # If no timezone selection is returned, try to get the default from configuration.
            if not timezone_data or not timezone_data.get("timezone_selection"):
                self.logger.info("No timezone data received, attempting to use default from config")
                default_timezone = None
                for dropdown in self.config["timezone_dropdown"].get("dropdowns", []):
                    for option in dropdown.get("options", []):
                        if option.get("default"):
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
                event_data["event_date"],
                event_data["event_time"],
                timezone
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
                    reactions=EventReactions(yes=0, no=0, maybe=0)
                )
            )

            # Save the event to the database
            db.add_document(new_event)
            self.logger.info(f"Event saved to database with ID {event_id}")

            # Update the guild document to include this event
            guild = db.get_document(Guild, interaction.guild_id)
            if not guild:
                guild = Guild(_id=interaction.guild_id, events=[])
                db.add_document(guild)
            elif not hasattr(guild, 'events'):
                guild.events = []

            guild.events.append(event_id)
            db.update_document(guild, {"events": guild.events})
            self.logger.info(f"Guild document updated with event ID {event_id}")

            # Show the event details
            await self.show_event_embed(dropdown_message, new_event)
            self.logger.info(f"Event '{event_data['event_name']}' created with ID {event_id}")

        except Exception as e:
            self.logger.error(f"Exception in create_event: {e}", exc_info=True)
            if interaction.response.is_done():
                await interaction.followup.send(f"Error creating event: {str(e)}", ephemeral=True)
            else:
                await interaction.response.send_message(f"Error creating event: {str(e)}", ephemeral=True)

    async def list_events(self, interaction: discord.Interaction) -> None:
        """List all upcoming events for the guild."""
        self.logger.info(f"Listing events for guild {interaction.guild_id}")

        guild = db.get_document(Guild, interaction.guild_id)
        if not guild or not hasattr(guild, 'events') or not guild.events:
            self.logger.info(f"No events found for guild {interaction.guild_id}")
            await interaction.followup.send("No events found for this server.", ephemeral=True)
            return

        # Get all upcoming events from guild's event list
        current_time = self.now()
        guild_events = []

        self.logger.info(f"Found {len(guild.events)} events for guild {interaction.guild_id}")
        for event_id in guild.events:
            event = db.get_document(Event, event_id)
            if event and hasattr(event, 'details'):
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
            color=discord.Color.blue()
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
                inline=False
            )

        await interaction.followup.send(embed=embed, ephemeral=True)

    async def get_event_selection(self, interaction: discord.Interaction, action: str) -> tuple[Optional[Event], Optional[discord.Message]]:
        """Get event selection from dropdown. Returns (Event, Message) or (None, None)."""
        message: Optional[discord.Message] = None  # Initialize message variable
        try:
            # Get all events for this guild
            guild = db.get_document(Guild, interaction.guild_id)
            if not guild or not hasattr(guild, 'events') or not guild.events:
                try:
                    # Attempt to respond if not already done
                    target = interaction.followup if interaction.response.is_done() else interaction.response
                    await target.send("No events found for this server.", ephemeral=True)
                except (discord.NotFound, discord.HTTPException) as e:
                    self.logger.warning(f"Could not send 'no events' message: {e}")
                return None, None  # Return None for both event and message

            # Get all upcoming events (or all for delete)
            current_time = self.now()
            guild_events = []

            for event_id in guild.events:
                event = db.get_document(Event, event_id)
                if event and hasattr(event, 'details'):
                    event_time = event.details.time
                    if event_time.tzinfo is None:
                        event_time = pytz.UTC.localize(event_time)
                    if action == "delete" or event_time >= current_time:
                        guild_events.append(event)

            if not guild_events:
                try:
                    # Attempt to respond if not already done
                    target = interaction.followup if interaction.response.is_done() else interaction.response
                    await target.send("No matching events found.", ephemeral=True)
                except (discord.NotFound, discord.HTTPException) as e:
                    self.logger.warning(f"Could not send 'no matching events' message: {e}")
                return None, None  # Return None for both event and message

            # Create dropdown options
            options = []
            for event in guild_events:
                options.append({
                    "label": f"{event.details.name}",
                    "description": self.format_datetime(event.details.time)[:99],  # Ensure description fits
                    "value": str(event._id)
                })

            # Create dropdown config
            dropdown_config = {
                "ephemeral": True,
                "add_buttons": True,
                "timeout": 180,
                "dropdowns": [{
                    "custom_id": "event_selection",
                    "placeholder": f"Select an event to {action}",
                    "min_values": 1,
                    "max_values": 1,
                    "selections": options
                }]
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
                        wait=True
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
                        interaction,
                        f"Please select an event to {action}:"
                    )
            except (discord.NotFound, discord.HTTPException) as e:
                self.logger.warning(f"Interaction/HTTP error during event selection for {action}: {e}")
                # Cannot edit message if interaction expired, return None, None
                return None, None
            except Exception as e:
                self.logger.error(f"Unexpected error during dropdown view handling: {e}", exc_info=True)
                # Ensure we return two Nones
                return None, None

            # --- Process the selection ---
            if not view.accepted or not values or not message:
                # User cancelled, timed out, or interaction failed
                if message and not view.is_finished():  # Check if view finished itself
                    try:
                        await message.edit(content="Event selection cancelled or timed out.", view=None, embed=None)
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
                    await message.edit(content=f"Error: Invalid event ID selected ({selected_id_str}).", view=None, embed=None)
                except (discord.NotFound, discord.HTTPException):
                    pass
                return None, None  # Return None for both

            # Fetch the event document
            selected_event = db.get_document(Event, selected_id)
            if not selected_event:
                # Event ID was valid int but not found in DB (maybe deleted?)
                self.logger.warning(f"Selected event ID {selected_id} not found in database.")
                try:
                    await message.edit(content=f"Error: Event with ID {selected_id} not found.", view=None, embed=None)
                except (discord.NotFound, discord.HTTPException):
                    pass
                return None, message  # Return None for event, but keep message context

            # Success: Return the event document and the message
            return selected_event, message

        except Exception as e:
            self.logger.error(f"Outer error in get_event_selection: {str(e)}", exc_info=True)
            # Ensure we return two values even on unexpected error
            # Try to inform user if possible
            try:
                target = interaction.followup if interaction.response.is_done() else interaction.response
                await target.send("An unexpected error occurred while selecting the event.", ephemeral=True)
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
                embed=None
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
                    embed=None  # Ensure embed is cleared
                )
            else:  # Cancelled delete
                await message.edit(
                    content="Event deletion cancelled.",
                    view=None,
                    embed=None  # Ensure embed is cleared
                )
        except (discord.NotFound, discord.HTTPException) as e:
            self.logger.warning(f"Failed to edit message after delete confirmation: {e}")
            # Log deletion status if possible
            if view.value:
                self.logger.info(f"Event {event._id} was deleted, but confirmation message failed.")
            else:
                self.logger.info(f"Event {event._id} deletion was cancelled, but cancellation message failed.")

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
                embed=None
            )
        except (discord.NotFound, discord.HTTPException) as e:
            self.logger.warning(f"Failed to edit message for announce confirmation: {e}")
            return  # Can't proceed if message is gone

        await view.wait()

        # Check if announcement was cancelled early
        if not view.value:
            try:
                await message.edit(
                    content="Event announcement cancelled.",
                    view=None,
                    embed=None  # Clear embed
                )
            except (discord.NotFound, discord.HTTPException):
                pass  # Best effort
            return

        # Find or create announcements channel
        announcement_channel = discord.utils.get(interaction.guild.text_channels, name="announcements")  # Use your actual channel name

        if not announcement_channel:
            try:
                await message.edit(
                    content="Error: Could not find or create the announcements channel.",
                    view=None,
                    embed=None
                )
            except (discord.NotFound, discord.HTTPException):
                pass
            return

        # Create announcement embed
        embed = discord.Embed(
            title=f"📅 Event: {event.details.name}",
            description=event.details.description,
            color=discord.Color.blue()
        )

        # Add event details
        localized_time = self.format_datetime(event.details.time)
        embed.add_field(name="Date/Time", value=localized_time, inline=True)
        embed.add_field(name="Location", value=event.details.location, inline=True)

        # Add footer with instructions
        embed.set_footer(text="React with ✅ to attend, ❌ if you can't make it, or ❔ if you're unsure.")

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
                embed=None  # Clear embed
            )
        except discord.Forbidden:
            self.logger.error(f"Permission error announcing event {event._id} in channel {announcement_channel.id}")
            try:
                await message.edit(
                    content="Error: I don't have permission to send messages or add reactions in the announcements channel.",
                    view=None,
                    embed=None  # Clear embed
                )
            except (discord.NotFound, discord.HTTPException):
                pass
        except Exception as e:
            self.logger.error(f"Error during event announcement send/react: {e}", exc_info=True)
            try:
                await message.edit(
                    content="An error occurred while sending the announcement.",
                    view=None,
                    embed=None  # Clear embed
                )
            except (discord.NotFound, discord.HTTPException):
                pass

    async def my_events(self, interaction: discord.Interaction) -> None:
        """Show events the user is registered for with registration status."""
        user = db.get_document(User, interaction.user.id)
        if not user or not hasattr(user, 'events') or not user.events:
            await interaction.followup.send(
                "You're not registered for any events.",
                ephemeral=True
            )
            return

        # Get all events the user is registered for
        user_events = []
        current_time = self.now()

        for event_id in user.events:
            event = db.get_document(Event, event_id)
            if event and hasattr(event, 'details'):
                event_time = event.details.time
                # If the event time is offset-naive, assume it's in UTC
                if event_time.tzinfo is None:
                    event_time = pytz.UTC.localize(event_time)
                if event_time >= current_time:
                    user_events.append(event)

        if not user_events:
            await interaction.followup.send(
                "You're not registered for any upcoming events.",
                ephemeral=True
            )
            return

        # Sort events by datetime
        user_events.sort(key=lambda e: e.details.time)

        # Create an embed to display the events
        embed = discord.Embed(
            title="Your Events",
            description=f"You are registered for {len(user_events)} upcoming events",
            color=discord.Color.green()
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
                inline=False
            )

        await interaction.followup.send(embed=embed, ephemeral=True)

    async def show_event_embed(
        self,
        message_or_interaction: Union[discord.Message, discord.Interaction],
        event: Event,
    ) -> None:
        """Display event details in an embed."""
        is_message = isinstance(message_or_interaction, discord.Message)

        # Create the embed
        embed = discord.Embed(
            title=event.details.name,
            description=event.details.description,
            color=discord.Color.purple(),
        )

        # Add event details as fields
        localized_time = self.format_datetime(event.details.time)
        embed.add_field(name="Date/Time", value=localized_time, inline=True)
        embed.add_field(name="Location", value=event.details.location, inline=True)

        # Add attendance information using the yes_users list
        total_attendees = len(event.yes_users)
        embed.add_field(name="Attendees", value=str(total_attendees), inline=True)

        if hasattr(event.details, 'reactions'):
            reactions_text = f"✅ Yes: {event.details.reactions.yes} | ❌ No: {event.details.reactions.no} | ❔ Maybe: {event.details.reactions.maybe}"
            embed.add_field(name="RSVPs", value=reactions_text, inline=False)

        # Add event ID as footer
        embed.set_footer(text=f"Event ID: {event._id}")

        # Send or edit message based on the context
        if is_message:
            await message_or_interaction.edit(content=None, embed=embed, view=None)
        else:
            await message_or_interaction.followup.send(embed=embed, ephemeral=True)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload) -> None:
        """Handle reactions to event announcements."""
        # Ignore bot reactions
        if payload.user_id == self.bot.user.id:
            return

        # Check if this is a reaction to an event announcement
        channel = self.bot.get_channel(payload.channel_id)
        if not channel:
            return

        try:
            message = await channel.fetch_message(payload.message_id)
        except (discord.NotFound, discord.Forbidden):
            return

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
        if not hasattr(user, 'events'):
            user.events = []

        # Ensure event is in user's list
        if event._id not in user.events:
            user.events.append(event._id)
            user.save()
            self.logger.info(f"Updated user {user_id} for event {event._id} with 'yes' response.")

    async def handle_attendance_remove(self, user_id: int, event: Event) -> None:
        """Handle marking a user with "no" response (not attending)."""
        user = db.get_document(User, user_id)

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

        # Handle user document updates - a "no" response means removing the event from the user's list
        if hasattr(user, 'events') and event._id in user.events:
            user.events.remove(event._id)
            user.save()
            self.logger.info(f"Removed event {event._id} from user {user_id}'s event list.")

    async def handle_attendance_maybe(self, user_id: int, event: Event) -> None:
        """Handle marking a user as maybe for event attendance."""
        user = db.get_document(User, user_id)

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
        if payload.user_id == self.bot.user.id:
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
            self.logger.error(f"Error finding event by message_id {payload.message_id}: {e}")
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
                    event.details.reactions.yes = max(0, event.details.reactions.yes - 1)
                modified = True

                # Remove event from user's list
                user = db.get_document(User, user_id)
                if user and hasattr(user, 'events') and event._id in user.events:
                    user.events.remove(event._id)
                    user.save()
                    self.logger.info(f"Removed event {event._id} from user {user_id}'s event list after reaction removal.")

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
                    event.details.reactions.maybe = max(0, event.details.reactions.maybe - 1)
                modified = True

                # Remove event from user's list
                user = db.get_document(User, user_id)
                if user and hasattr(user, 'events') and event._id in user.events:
                    user.events.remove(event._id)
                    user.save()
                    self.logger.info(f"Removed event {event._id} from user {user_id}'s event list after maybe reaction removal.")

        # Save the event document if modified
        if modified:
            event.save()
            self.logger.info(f"Updated event {event._id} for user {user_id} after reaction removal.")

    async def edit_event_selection(self, interaction: discord.Interaction) -> None:

        # Interaction already deferred
        event, message = await self.get_event_selection(interaction, "edit")
        if not event or not message:  # Check both event and message
            # Error/cancel message already handled within get_event_selection if possible
            return

        # At this point, we have both the event and the message
        # Let's modify edit_event to go straight to showing the modal
        await self.edit_event(interaction, event, message)

        # Get all events for this guild
        guild = db.get_document(Guild, interaction.guild_id)
        if not guild or not hasattr(guild, 'events') or not guild.events:
            await interaction.response.send_message("No events found for this server.", ephemeral=True)
            return

        # Get all upcoming events
        current_time = self.now()
        guild_events = []

        for event_id in guild.events:
            event = db.get_document(Event, event_id)
            if event and hasattr(event, 'details'):
                event_time = event.details.time
                if event_time.tzinfo is None:
                    event_time = pytz.UTC.localize(event_time)
                if event_time >= current_time:
                    guild_events.append(event)

        if not guild_events:
            await interaction.response.send_message("No upcoming events found.", ephemeral=True)
            return

        # Create dropdown options
        options = []
        for event in guild_events:
            options.append({
                "label": f"{event.details.name}",
                "description": self.format_datetime(event.details.time)[:99],
                "value": str(event._id)
            })

        # Create dropdown config
        dropdown_config = {
            "ephemeral": True,
            "add_buttons": True,
            "timeout": 180,
            "dropdowns": [{
                "custom_id": "event_selection",
                "placeholder": "Select an event to edit",
                "min_values": 1,
                "max_values": 1,
                "selections": options
            }]
        }

        # Create dropdown view
        view = DynamicDropdownView(**dropdown_config)

        # Send the dropdown message
        await interaction.response.send_message(
            "Please select an event to edit:",
            view=view,
            ephemeral=True
        )

        # Wait for selection
        await view.wait()

        # Get selected values
        selections = {}
        for dropdown in view._dropdowns:
            if dropdown.selected_values:
                selections[dropdown.custom_id] = dropdown.selected_values

        values = selections if view.accepted else None

        # Get the message for later use
        try:
            message = await interaction.original_response()
        except (discord.NotFound, discord.HTTPException):
            return  # Can't proceed if message is gone

        # Check if a selection was made
        if not view.accepted or not values or not message:
            # User cancelled, timed out, or interaction failed
            try:
                await message.edit(content="Event selection cancelled or timed out.", view=None, embed=None)
            except (discord.NotFound, discord.HTTPException):
                pass  # Ignore if message is already gone
            return

        # Get the selected event ID
        selected_id_str = values.get("event_selection", [None])[0]
        if not selected_id_str:
            return

        # Convert ID to int
        try:
            selected_id = int(selected_id_str)
        except ValueError:
            self.logger.error(f"Invalid event ID selected: {selected_id_str}")
            await message.edit(content=f"Error: Invalid event ID selected ({selected_id_str}).", view=None, embed=None)
            return

        # Fetch the event document
        selected_event = db.get_document(Event, selected_id)
        if not selected_event:
            self.logger.warning(f"Selected event ID {selected_id} not found in database.")
            await message.edit(content=f"Error: Event with ID {selected_id} not found.", view=None, embed=None)
            return

        # At this point we have the event and the message, so call edit_event
        await self.edit_event(interaction, selected_event, message)

    async def edit_event(self, interaction: discord.Interaction, event: Event, message: discord.Message) -> None:
        """Edit a specific event."""
        self.logger.info(f"Event edit requested for event {event._id} by {interaction.user}")

        try:
            # Prepare initial data for the modal
            init_data = {
                "event_name": event.details.name,
                "event_description": event.details.description or "",
                "event_location": event.details.location or "",
            }

            # Format date and time for the modal
            event_time = event.details.time
            if event_time.tzinfo is None:
                # If time has no timezone, assume it's UTC
                event_time = pytz.UTC.localize(event_time)

            # Convert the time to Eastern Time for display since you're in EST
            eastern_tz = pytz.timezone('US/Eastern')
            eastern_time = event_time.astimezone(eastern_tz)

            # Format date as MM/DD/YY using the Eastern time
            init_data["event_date"] = eastern_time.strftime("%m/%d/%y")

            # Format time as HH:MM AM/PM using the Eastern time
            init_data["event_time"] = eastern_time.strftime("%I:%M %p")

            # Edit message to show editing status
            await message.edit(
                content=f"Editing event '{event.details.name}'...",
                embed=None,
                view=None
            )

            # Create the button modal view
            button_modal_view = ButtonDynamicModalView(
                button_label="Edit Event Details",
                message_prompt=f"Click the button below to edit event '{event.details.name}'",
                modal=self.config["edit_event_modal"]["modal"],
                ephemeral=True
            )

            # Set default values for fields
            for field in button_modal_view._modal.children:
                if field.custom_id in init_data:
                    field.default = init_data[field.custom_id]

            # Show the button that will trigger the modal
            event_data, modal_message = await button_modal_view.initiate_from_message(message)

            # If modal was cancelled or timed out
            if not event_data:
                await message.edit(content="Event edit cancelled.", embed=None, view=None)
                return

            # Validate the form data
            if not self._validate_event_form(event_data):
                await modal_message.edit(
                    content="Invalid event data. Please check date/time formats and try again.",
                    view=None
                )
                return

            # Prepare the timezone dropdown configuration
            timezone_config = self.config["timezone_dropdown"].copy()
            timezone_config.pop("placeholder", None)

            if "dropdowns" in timezone_config:
                new_dropdowns = []
                for dropdown in timezone_config["dropdowns"]:
                    if "options" in dropdown:
                        dropdown["selections"] = dropdown.pop("options")
                    new_dropdowns.append(dropdown)
                timezone_config["dropdowns"] = new_dropdowns

            # Get timezone selection with dropdown
            timezone_view = DynamicDropdownView(**timezone_config)
            timezone_data, dropdown_message = await timezone_view.initiate_from_message(
                modal_message or message,
                "Please select a timezone for the event:"
            )

            # If no timezone selection is returned, use default
            if not timezone_data or not timezone_data.get("timezone_selection"):
                # Find default from configuration
                default_timezone = None
                for dropdown in self.config["timezone_dropdown"].get("dropdowns", []):
                    for option in dropdown.get("options", []):
                        if option.get("default"):
                            default_timezone = option.get("value")
                            break
                    if default_timezone:
                        break
                if not default_timezone:
                    default_timezone = "US/Eastern"
                timezone_data = {"timezone_selection": [default_timezone]}

            # Get timezone or use default
            timezone = timezone_data.get("timezone_selection", ["US/Eastern"])[0]

            # Parse the date and time into a datetime object
            event_time = self.parse_datetime(
                event_data["event_date"],
                event_data["event_time"],
                timezone
            )

            # Create a new EventDetails object with updated values
            new_details = EventDetails(
                name=event_data["event_name"],
                description=event_data["event_description"],
                time=event_time,
                location=event_data["event_location"],
                reactions=event.details.reactions  # Keep the existing reactions
            )

            # Update the entire details field
            event.details = new_details
            event.save()

            self.logger.info(f"Event {event._id} updated successfully")

            # Show the updated event details
            message_to_update = dropdown_message or modal_message or message

            # Update the message channel if the event has been announced
            if event.message_id > 0:
                try:
                    # Find the announcement message
                    for guild in self.bot.guilds:
                        for channel in guild.text_channels:
                            try:
                                announcement = await channel.fetch_message(event.message_id)
                                if announcement:
                                    # Update the announcement embed
                                    embed = announcement.embeds[0]
                                    embed.title = f"📅 Event: {event.details.name}"
                                    embed.description = event.details.description

                                    # Clear existing fields and add updated ones
                                    embed.clear_fields()

                                    localized_time = self.format_datetime(event.details.time)
                                    embed.add_field(name="Date/Time", value=localized_time, inline=True)
                                    embed.add_field(name="Location", value=event.details.location, inline=True)

                                    # Add footer with instructions
                                    embed.set_footer(text="React with ✅ to attend, ❌ if you can't make it, or ❔ if you're unsure.")

                                    # Update the message
                                    await announcement.edit(embed=embed)
                                    self.logger.info(f"Announcement for event {event._id} updated")
                                    break
                            except (discord.NotFound, discord.Forbidden, Exception) as e:
                                continue
                except Exception as e:
                    self.logger.error(f"Error updating announcement for event {event._id}: {e}")

            # Show the updated event details to the user
            await self.show_event_embed(message_to_update, event)

        except Exception as e:
            self.logger.error(f"Exception in edit_event: {e}", exc_info=True)
            await message.edit(
                content=f"Error editing event: {str(e)}",
                embed=None,
                view=None
            )


async def setup(bot: commands.Bot) -> None:
    """Set up the Event cog."""
    await bot.add_cog(EventCog(bot))

"""Event management cog for handling events."""

import logging
import re
from typing import Union, Dict, Optional, List
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
from frontend.interactions.bases.modal_base import DynamicModalView
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

    def parse_datetime(self, date_str: str, time_str: str, timezone_str: str = None) -> datetime:
        """Parse date and time strings into a datetime object."""
        try:
            # Extract timezone from time string if not provided separately
            if timezone_str is None and len(time_str.split()) > 2:
                time_parts = time_str.split()
                timezone_str = time_parts[-1]
                time_str = " ".join(time_parts[:-1])

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
        ]
    )
    async def event(self, interaction: discord.Interaction, action: str) -> None:
        """Handle event actions."""
        if action == "create":
            await self.create_event(interaction)
        elif action == "list":
            await interaction.response.defer(ephemeral=True)
            await self.list_events(interaction)
        elif action == "show":
            await self.show_event_selection(interaction)
        elif action == "delete":
            await self.delete_event_selection(interaction)
        elif action == "announce":
            await self.announce_event_selection(interaction)
        elif action == "myevents":
            await interaction.response.defer(ephemeral=True)
            await self.my_events(interaction)

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

            # Create the event document
            new_event = Event(
                _id=event_id,
                guild_id=interaction.guild_id,
                users=[],
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
            else:
                if not hasattr(guild, 'events'):
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
            
            # Add field for each event
            embed.add_field(
                name=f"{event.details.name} (ID: {event._id})",
                value=f"**When:** {localized_time}\n**Where:** {event.details.location}\n**Attendees:** {len(event.users)}",
                inline=False
            )
            
        await interaction.followup.send(embed=embed, ephemeral=True)


    async def handle_attendance_add(self, user_id: int, message_id: int):
        """Handles adding a user to event attendance."""
        user = db.get_document(User, user_id)
        if not user:
            self.logger.warning(f"User ID {user_id} not found.")
            return

        # Find event by message_id
        event = self.find_event_by_message_id(message_id)
        if not event:
            return

        if hasattr(user, 'events') and event.id in user.events:
            self.logger.info(f"User {user_id} already registered for event {event.id}.")
            return

        # Update reactions count
        if not hasattr(event, 'reactions'):
            event.reactions = {"yes": 0, "no": 0, "maybe": 0}
        event.reactions["yes"] += 1

        # Update attendance
        if not hasattr(event, 'users'):
            event.users = []
        event.users.append(user_id)

        if not hasattr(user, 'events'):
            user.events = []
        user.events.append(event.id)

        # Save changes
        db.update_document(event)
        db.update_document(user)
        self.logger.info(f"User {user_id} added to event {event.id}.")

    def find_event_by_message_id(self, message_id: int) -> Event:
        """Helper method to find an event by its message ID."""
        all_events = Event.objects.all()
        for event in all_events:
            if hasattr(event, 'message_id') and event.message_id == message_id:
                return event
        return None

    async def handle_attendance_remove(self, user_id: int, message_id: int):
        """Handles removing a user from event attendance."""
        user = db.get_document(User, user_id)
        if not user:
            self.logger.warning(f"User ID {user_id} not found.")
            return

        event = self.find_event_by_message_id(message_id)
        if not event:
            return

        # Update reactions count
        if hasattr(event, 'reactions'):
            if hasattr(event, 'users') and user_id in event.users:
                event.reactions["yes"] -= 1
            event.reactions["no"] += 1

        # Remove user from event
        if hasattr(user, 'events') and event.id in user.events:
            user.events.remove(event.id)
        if hasattr(event, 'users') and user_id in event.users:
            event.users.remove(user_id)

        # Save changes
        db.update_document(event)
        db.update_document(user)
        self.logger.info(f"User {user_id} removed from event {event.id}.")

    async def handle_attendance_maybe(self, user_id: int, message_id: int):
        """Handles marking a user as maybe for event attendance."""
        user = db.get_document(User, user_id)
        if not user:
            self.logger.warning(f"User ID {user_id} not found.")
            return

        event = self.find_event_by_message_id(message_id)
        if not event:
            return

        # Update reactions count
        if not hasattr(event, 'reactions'):
            event.reactions = {"yes": 0, "no": 0, "maybe": 0}
        event.reactions["maybe"] += 1

        # Save changes
        db.update_document(event)
        self.logger.info(f"User {user_id} marked as maybe for event {event.id}.")

    async def ask_event_name(self, ctx):
        """Asks for and validates the event name."""
        try:
            await ctx.send("Please enter the event name:")
            msg = await self.bot.wait_for(
                "message", 
                check=lambda m: m.author == ctx.author,
                timeout=60
            )
            self.logger.info(f"Event name received: {msg.content}")
            return msg.content
        except TimeoutError:
            await ctx.send("You took too long to respond. Please try again.")
            return None

    async def ask_event_description(self, ctx):
        """Asks for and validates the event description."""
        try:
            await ctx.send("Please enter the event description:")
            msg = await self.bot.wait_for(
                "message", 
                check=lambda m: m.author == ctx.author,
                timeout=60
            )
            self.logger.info(f"Event description received: {msg.content}")
            return msg.content
        except TimeoutError:
            await ctx.send("You took too long to respond. Please try again.")
            return None

    async def ask_event_date(self, ctx):
        """Asks for and validates the event date."""
        date_pattern = re.compile(r"^(0[1-9]|1[0-2])\/(0[1-9]|[12][0-9]|3[01])\/\d{2}$")

        while True:
            try:
                await ctx.send("Please enter the event date in mm/dd/yy format (e.g., 12/31/24):")
                msg = await self.bot.wait_for(
                    "message", 
                    check=lambda m: m.author == ctx.author,
                    timeout=60
                )
                date_input = msg.content.strip()

                if date_pattern.match(date_input):
                    self.logger.info(f"Event date received: {date_input}")
                    return date_input
                else:
                    await ctx.send("Invalid date format. Please use mm/dd/yy format.")
            except TimeoutError:
                await ctx.send("You took too long to respond. Please try again.")
                return None

    async def ask_event_time(self, ctx):
        """Asks for and validates the event time."""
        time_pattern = re.compile(r"^(0[1-9]|1[0-2]):[0-5][0-9] (AM|PM)( [A-Z]{2,4})?$")

        while True:
            try:
                await ctx.send(
                    "Please enter the event time in 'HH:MM AM/PM Timezone' format\n"
                    "Example: 12:00 PM PDT (Timezone is optional, defaults to EDT)"
                )
                msg = await self.bot.wait_for(
                    "message", 
                    check=lambda m: m.author == ctx.author,
                    timeout=60
                )
                time_input = msg.content.strip()

                if time_pattern.match(time_input):
                    self.logger.info(f"Event time received: {time_input}")
                    return time_input
                else:
                    await ctx.send("Invalid time format.")
            except TimeoutError:
                await ctx.send("You took too long to respond. Please try again.")
                return None

    async def ask_event_location(self, ctx):
        """Asks for and validates the event location."""
        try:
            await ctx.send("Please enter the event location:")
            msg = await self.bot.wait_for(
                "message", 
                check=lambda m: m.author == ctx.author,
                timeout=60
            )
            self.logger.info(f"Event location received: {msg.content}")
            return msg.content
        except TimeoutError:
            await ctx.send("You took too long to respond. Please try again.")
            return None

    @events.command(name="show", help="Show details of a specific event.")
    async def show_event(self, ctx, event_id: int):
        """Displays the details of a specific event by its ID."""
        self.logger.info(f"User {ctx.author} requested details for event ID: {event_id}.")

        event = db.get_document(Event, event_id)
        if not event:
            await ctx.send(f"No event found with ID: {event_id}.")
            return

        embed = self.create_event_embed(event)
        await ctx.send(embed=embed)

    def create_event_embed(self, event: Event):
        """Creates an embed for a single event."""
        embed = discord.Embed(
            title=event.name,
            description=event.description,
            color=discord.Color.blue(),
        )
        embed.add_field(
            name="Date/Time", 
            value=self.localize_datetime(event.datetime, event.timezone), 
            inline=True
        )
        embed.add_field(name="Location", value=event.location, inline=True)
        embed.add_field(name="Event ID", value=str(event.id), inline=False)
        return embed

    @events.command(name="clear", help="Clears all upcoming events.")
    async def clear_events(self, ctx):
        """Deletes all future guild events."""
        self.logger.info(f"User {ctx.author} is clearing all events for guild {ctx.guild.id}.")
        
        current_time = self.now()
        guild = db.get_document(Guild, ctx.guild.id)
        
        if guild and hasattr(guild, 'events'):
            # Get all events
            for event_id in guild.events:
                event = db.get_document(Event, event_id)
                if event and event.datetime > current_time:
                    db.soft_delete_document(Event, event_id)
            
            # Clear guild's event list
            guild.events = []
            db.update_document(guild)
        
        embed = discord.Embed(
            title="Events Cleared",
            description="All events have been successfully cleared.",
            color=discord.Color.orange(),
        )
        await ctx.send(embed=embed)
        self.logger.info("All events cleared successfully.")

    @events.command(name="myevents", help="Get events you are registered for.")
    async def my_events(self, ctx):
        """Shows events the user is registered for."""
        self.logger.info(f"User {ctx.author.id} requested their registered events.")

        user = db.get_document(User, ctx.author.id)
        if not user or not hasattr(user, 'events') or not user.events:
            await self.send_no_events_embed(ctx)
            self.logger.info(f"User {ctx.author.id} has no registered events.")
            return

        user_events = []
        for event_id in user.events:
            event = db.get_document(Event, event_id)
            if event:
                user_events.append(event)

        if not user_events:
            await self.send_no_events_embed(ctx)
            return

        await ctx.author.send(embed=self.create_events_embed(user_events))
        self.logger.info(f"Sent registered events to user {ctx.author.id}.")

    @commands.command(name="announce", help="Announces an event in the announcements channel.")
    async def announce(self, ctx, event_id: int):
        """Announces an event in the announcements channel."""
        event = db.get_document(Event, event_id)
        if not event:
            await ctx.send("ERROR: Event not found.")
            return

        # Find or create announcements channel
        announcement_channel = discord.utils.get(ctx.guild.text_channels, name="announcements")
        if announcement_channel is None:
            try:
                announcement_channel = await ctx.guild.create_text_channel("announcements")
                await announcement_channel.set_permissions(ctx.guild.default_role, send_messages=False)
                await announcement_channel.set_permissions(ctx.guild.me, send_messages=True)
            except discord.Forbidden:
                await ctx.send("ERROR: I do not have permission to create channels.")
                return

        # Create announcement embed
        embed = discord.Embed(
            title="Event Announcement",
            description=(
                f"**Event:** {event.name}\n"
                f"**Date/Time:** {self.localize_datetime(event.datetime, event.timezone)}\n"
                f"**Location:** {event.location}\n\n"
                "React with ✅ to attend, ❌ to decline, or ❔ for maybe."
            ),
            color=discord.Color.purple(),
        )

        try:
            message = await announcement_channel.send(embed=embed)
            for reaction in self.allowed_reactions:
                await message.add_reaction(reaction)
            
            # Save message ID to event
            event.message_id = message.id
            db.update_document(event)
            
            await ctx.send(f"Event announced in #{announcement_channel.name}!")
            self.logger.info(f"Event announced successfully in #{announcement_channel.name} with message ID {message.id}.")
        
        except discord.Forbidden:
<<<<<<< HEAD:src/capy_app/frontend/cogs/event_cog.py
            await ctx.send("ERROR: I do not have permission to send messages or add reactions in the announcements channel.")
=======
            await ctx.send(
                "ERROR: I do not have permission to send messages or add reactions in the announcements channel."
            )

    # Function to handle adding attendance on reaction
    async def reaction_attendance_add(self, user_id, message_id):
        """Adds user to event attendance list."""

        #! fix the reactions, remove "yes" when a user changes their mind from no

        # Pull the user data
        user_data = self.bot.db.get_data("user", user_id)
        if not user_data:
            self.bot.logger.warning(
                f"reaction_attendance_add: User ID {user_id} not found."
            )
            return

        all_event_data = self.bot.db.get_paginated_data("event", 1, 10)

        # Not efficient search method for large data
        for row in all_event_data:
            if row.get_value("message_id") == message_id:
                event_id = row.get_value("id")
                break

        event_data = self.bot.db.get_data("event", event_id)

        if event_id in user_data.get_value("event"):
            self.bot.logger.warning(
                f"User ID {user_id} has already signed up for event ID {event_id}. No need to re-add."
            )
            return

        # Access the "reactions" field
        reactions = event_data.get_value("reactions")
        if reactions and isinstance(reactions, dict):
            # Increment the "yes" count
            reactions["yes"] += 1
            self.bot.logger.info(f"Updated Reactions: {reactions}")

            # Update the event data with the modified reactions
            event_data.set_value("reactions", reactions)
        else:
            self.bot.logger.warning(f"Invalid reactions field in event ID {event_id}.")
            return

        # Update the "user" key in the event's JSON data with user_id
        event_data.append_value("user", user_id)

        # Save the updated event data back to the database
        self.bot.db.upsert_data(event_data)

        # Update the "event" key in the user's JSON data with the event_id
        user_data.append_value("event", event_id)

        # Save the updated data back to the database
        self.bot.db.upsert_data(user_data)
        self.bot.logger.info(f"User {user_id} updated with event {event_id}.")

    # Function to handle removing attendance on reaction
    async def reaction_attendance_remove(self, user_id, message_id):
        """
        Removes user from event attendance list.
        """

        user_data = self.bot.db.get_data("user", user_id)
        if not user_data:
            self.bot.logger.warning(
                f"reaction_attendance_remove: User ID {user_id} not found."
            )
            return

        all_event_data = self.bot.db.get_paginated_data("event", 1, 10)

        # Not efficient search method for large data
        for row in all_event_data:
            if row.get_value("message_id") == message_id:
                event_id = row.get_value("id")
                break

        event_data = self.bot.db.get_data("event", event_id)

        # Access the "reactions" field
        reactions = event_data.get_value("reactions")
        if reactions and isinstance(reactions, dict):
            # Increment the "no" count
            reactions["no"] += 1

            # Update the event data with the modified reactions
            event_data.set_value("reactions", reactions)
        else:
            self.bot.logger.warning(f"Invalid reactions field in event ID {event_id}.")
            return

        # Check if the event is already removed or blank, do not remove again
        if event_id not in user_data.get_value("event"):
            self.bot.logger.info(
                f"User {user_id} is not attending event {event_id}, no need to remove."
            )
        else:
            user_data.remove_value("event", event_id)
            self.bot.logger.info(
                f"Event {event_id} has been removed from user {user_id}'s events."
            )

        if user_id not in event_data.get_value("user"):
            self.bot.logger.info(
                f"User {user_id} is not attending event {event_id}, no need to remove."
            )
        else:
            event_data.remove_value("user", user_id)
            self.bot.logger.info(
                f"User {user_id} has been removed from event {event_id}'s users."
            )
            if reactions and isinstance(reactions, dict):
                reactions["yes"] -= 1
                self.bot.logger.info(f"Updated Reactions: {reactions}")

        # Save the updated data back to the database
        self.bot.db.upsert_data(user_data)
        self.bot.db.upsert_data(event_data)

    # Function to handle adding maybe to reaction
    async def reaction_attendance_maybe(self, user_id, message_id):
        """
        Increment the "maybe" count in the event's JSON data.
        """

        user_data = self.bot.db.get_data("user", user_id)
        if not user_data:
            self.bot.logger.warning(
                f"reaction_attendance_maybe: User ID {user_id} not found."
            )
            return

        all_event_data = self.bot.db.get_paginated_data("event", 1, 10)

        # Not efficient search method for large data
        for row in all_event_data:
            if row.get_value("message_id") == message_id:
                event_id = row.get_value("id")
                break

        event_data = self.bot.db.get_data("event", event_id)

        # Access the "reactions" field
        reactions = event_data.get_value("reactions")
        if reactions and isinstance(reactions, dict):
            # Increment the "maybe" count
            reactions["maybe"] += 1
            self.logger.bot.info(f"Updated Reactions: {reactions}")

            # Update the event data with the modified reactions
            event_data.set_value("reactions", reactions)
        else:
            self.bot.logger.warning(f"Invalid reactions field in event ID {event_id}.")
            return

        self.bot.db.upsert_data(user_data)
        self.bot.db.upsert_data(event_data)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        """
        Listens for reaction to event announcements and calls the appropriate function.

        Handle adding a reaction to limit users to only one option.
        """

        # Ensure this is not the bot's reaction
        if payload.user_id == self.bot.user.id:
            return

        # Fetch the message where the reaction was added
        channel = self.bot.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)

        # Get the user's previous reactions on the message
        for reaction in message.reactions:
            if reaction.emoji != payload.emoji.name and payload.user_id in [
                user.id async for user in reaction.users()
            ]:
                # Remove the user's previous reaction if it's different from the new one
                await reaction.remove(self.bot.get_user(payload.user_id))

        if payload.emoji.name == "✅":
            await self.reaction_attendance_add(payload.user_id, payload.message_id)
        elif payload.emoji.name == "❌":
            await self.reaction_attendance_remove(payload.user_id, payload.message_id)
        elif payload.emoji.name == "❔":
            await self.reaction_attendance_maybe(payload.user_id, payload.message_id)

>>>>>>> origin/develop:src/capy_app/frontend/cogs/features/event_cog.py.future

# Setup function to load the cog
async def setup(bot: commands.Bot):
    await bot.add_cog(EventCog(bot))
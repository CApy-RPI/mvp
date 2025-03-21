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
            
            # Add field for each event
            embed.add_field(
                name=f"{event.details.name} (ID: {event._id})",
                value=f"**When:** {localized_time}\n**Where:** {event.details.location}\n**Attendees:** {len(event.users)}",
                inline=False
            )
            
        await interaction.followup.send(embed=embed, ephemeral=True)

    async def get_event_selection(self, interaction: discord.Interaction, action: str) -> Optional[Event]:
        """Get event selection from dropdown."""
        # Get all events for this guild
        guild = db.get_document(Guild, interaction.guild_id)
        if not guild or not hasattr(guild, 'events') or not guild.events:
            await interaction.response.send_message("No events found for this server.", ephemeral=True)
            return None
            
        # Get all upcoming events
        current_time = self.now()
        guild_events = []
        
        for event_id in guild.events:
            event = db.get_document(Event, event_id)
            if event and hasattr(event, 'details'):
                event_time = event.details.time
                # Ensure event time is offset-aware (defaulting to UTC if not)
                if event_time.tzinfo is None:
                    event_time = pytz.UTC.localize(event_time)
                if action == "delete" or event_time >= current_time:
                    guild_events.append(event)
                    
        if not guild_events:
            await interaction.response.send_message("No upcoming events found.", ephemeral=True)
            return None
            
        # Create dropdown options for events
        options = []
        for event in guild_events:
            options.append({
                "label": f"{event.details.name}",
                "description": self.format_datetime(event.details.time)[:25],  # Truncate if needed
                "value": str(event._id)
            })
            
        # Create dropdown config using "options"
        dropdown_config = {
            "ephemeral": True,
            "add_buttons": True,
            "dropdowns": [{
                "custom_id": "event_selection",
                "placeholder": f"Select an event to {action}",
                "min_values": 1,
                "max_values": 1,
                "options": options
            }]
        }
        
        # Convert "options" key to "selections" in dropdown configuration
        if "dropdowns" in dropdown_config:
            new_dropdowns = []
            for dropdown in dropdown_config["dropdowns"]:
                if "options" in dropdown:
                    dropdown["selections"] = dropdown.pop("options")
                new_dropdowns.append(dropdown)
            dropdown_config["dropdowns"] = new_dropdowns

        # Create dropdown view
        view = DynamicDropdownView(**dropdown_config)
        values, message = await view.initiate_from_interaction(
            interaction, 
            f"Please select an event to {action}:"
        )
        
        if not values or not message:
            return None
            
        # Get the selected event ID
        selected_id = values.get("event_selection", [None])[0]
        if not selected_id:
            return None
            
        # Return the event document
        return db.get_document(Event, int(selected_id))

    async def show_event_selection(self, interaction: discord.Interaction) -> None:
        """Show details of a specific event selected from dropdown."""
        event = await self.get_event_selection(interaction, "view")
        if not event:
            return
            
        # Get the message from the dropdown response
        message = await interaction.original_response()
        
        # Display the event details
        await self.show_event_embed(message, event)

    async def delete_event_selection(self, interaction: discord.Interaction) -> None:
        """Delete a specific event selected from dropdown."""
        event = await self.get_event_selection(interaction, "delete")
        if not event:
            return
            
        # Get the message from the dropdown response
        message = await interaction.original_response()
        
        # Show confirmation dialog
        view = ConfirmDeleteView(**self.config["confirm_delete"])
        await message.edit(
            content=f"⚠️ Are you sure you want to delete the event '{event.details.name}'?",
            view=view,
            embed=None
        )
        
        await view.wait()
        if view.value:
            # Delete the event
            guild = db.get_document(Guild, interaction.guild_id)
            if guild and hasattr(guild, 'events') and event._id in guild.events:
                guild.events.remove(event._id)
                db.update_document(guild)
                
            db.delete_document(event)
            
            # Notify creator and all attendees by removing from their events list
            if event.users:
                for user_id in event.users:
                    user = db.get_document(User, user_id)
                    if user and hasattr(user, 'events') and event._id in user.events:
                        user.events.remove(event._id)
                        db.update_document(user)
            
            await message.edit(
                content=f"Event '{event.details.name}' has been deleted.",
                view=None
            )
        else:
            await message.edit(
                content="Event deletion cancelled.",
                view=None
            )

    async def announce_event_selection(self, interaction: discord.Interaction) -> None:
        """Announce a specific event selected from dropdown."""
        event = await self.get_event_selection(interaction, "announce")
        if not event:
            return
            
        # Get the message from the dropdown response
        message = await interaction.original_response()
        
        # Use the regular ConfirmView for confirmation (instead of ConfirmDeleteView)
        view = ConfirmView(**self.config["confirm_announce"])
        
        await message.edit(
            content=f"Are you sure you want to announce the event '{event.details.name}' in the announcements channel?",
            view=view,
            embed=None
        )
        
        await view.wait()
        if not view.value:
            await message.edit(
                content="Event announcement cancelled.",
                view=None
            )
            return
            
        # Find or create announcements channel
        announcement_channel = discord.utils.get(interaction.guild.text_channels, name="announcements")
        if announcement_channel is None:
            try:
                announcement_channel = await interaction.guild.create_text_channel("announcements")
                await announcement_channel.set_permissions(interaction.guild.default_role, send_messages=False)
                await announcement_channel.set_permissions(interaction.guild.me, send_messages=True)
            except discord.Forbidden:
                await message.edit(
                    content="Error: I don't have permission to create or access an announcements channel.",
                    view=None
                )
                return
                
        # Create announcement embed
        config = self.config["announce_message"]
        embed = discord.Embed(
            title=config["title"],
            description=(
                f"**Event:** {event.details.name}\n"
                f"**Date/Time:** {self.format_datetime(event.details.time)}\n"
                f"**Location:** {event.details.location}\n\n"
                f"**Description:** {event.details.description}"
            ),
            color=config["color"]
        )
        embed.set_footer(text=config["footer"])
        
        try:
            # Send the announcement
            announcement = await announcement_channel.send(embed=embed)
            
            # Add reactions for attendance
            for reaction in self.allowed_reactions:
                await announcement.add_reaction(reaction)
                
            # Save message ID to event
            event.message_id = announcement.id
            db.update_document(event, {"message_id": announcement.id})
            
            await message.edit(
                content=f"Event announced in #{announcement_channel.name}!",
                view=None
            )
        except discord.Forbidden:
            await message.edit(
                content="Error: I don't have permission to send messages or add reactions in the announcements channel.",
                view=None
            )


    async def my_events(self, interaction: discord.Interaction) -> None:
        """Show events the user is registered for."""
        user = db.get_document(User, interaction.user.id)
        if not user or not hasattr(user, 'events') or not user.events:
            await interaction.followup.send(
                "You're not registered for any events.",
                ephemeral=True
            )
            return
            
        # Get all events the user is registered for
        user_events = []
        for event_id in user.events:
            event = db.get_document(Event, event_id)
            if event and hasattr(event, 'details'):
                user_events.append(event)
                
        if not user_events:
            await interaction.followup.send(
                "You're not registered for any valid events.",
                ephemeral=True
            )
            return
            
        # Sort events by datetime
        user_events.sort(key=lambda e: e.details.time)
        
        # Create an embed to display the events
        embed = discord.Embed(
            title="Your Events",
            description=f"You are registered for {len(user_events)} events",
            color=discord.Color.green()
        )
        
        for event in user_events:
            # Format date for display
            localized_time = self.format_datetime(event.details.time)
            
            # Add field for each event
            embed.add_field(
                name=event.details.name,
                value=f"**When:** {localized_time}\n**Where:** {event.details.location}",
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
        
        # Add attendance information if available
        embed.add_field(name="Attendees", value=str(len(event.users)), inline=True)
        
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
            
        # Find event by message_id using MongoEngine's query interface
        event = Event.objects(message_id=payload.message_id).first()
        if not event:
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
        """Handle adding a user to event attendance."""
        # Get user document; if not registered, log and exit.
        user = db.get_document(User, user_id)
        if not user:
            self.logger.info(f"User {user_id} not registered; ignoring attendance add.")
            return
            
        # Check if user is already attending
        if event._id in user.events:
            return
            
        # Update the event's reactions
        event.details.reactions.yes += 1
            
        # Update attendance lists
        if user_id not in event.users:
            event.users.append(user_id)
        if event._id not in user.events:
            user.events.append(event._id)
            
        # Save changes
        db.update_document(event, {"details.reactions": event.details.reactions, "users": event.users})
        db.update_document(user, {"events": user.events})


    async def handle_attendance_remove(self, user_id: int, event: Event) -> None:
        """Handle removing a user from event attendance."""
        # Get user document; if not registered, log and exit.
        user = db.get_document(User, user_id)
        if not user:
            self.logger.info(f"User {user_id} not registered; ignoring attendance removal.")
            return
        
        # Update the event's reactions if user was marked as attending
        if user_id in event.users:
            event.details.reactions.yes -= 1
            
        # Remove user from event's user list if they were attending
        if user_id in event.users:
            event.users.remove(user_id)
            
        # Remove event from user's events list if present
        if event._id in user.events:
            user.events.remove(event._id)
            
        # Increment no reactions
        event.details.reactions.no += 1
            
        # Save changes
        db.update_document(event, {"details.reactions": event.details.reactions, "users": event.users})
        db.update_document(user, {"events": user.events})

    async def handle_attendance_maybe(self, user_id: int, event: Event) -> None:
        """Handle marking a user as maybe for event attendance."""
        # Get user document; if not registered, log and exit.
        user = db.get_document(User, user_id)
        if not user:
            self.logger.info(f"User {user_id} not registered; ignoring maybe attendance.")
            return
        
        # Update reactions count if user was previously attending
        if user_id in event.users:
            event.details.reactions.yes -= 1
            event.users.remove(user_id)
            
        # Remove from user's events list
        if event._id in user.events:
            user.events.remove(event._id)
            
        # Increment maybe count
        event.details.reactions.maybe += 1
            
        # Save changes
        db.update_document(event, {"details.reactions": event.details.reactions, "users": event.users})
        db.update_document(user, {"events": user.events})


async def setup(bot: commands.Bot) -> None:
    """Set up the Event cog."""
    await bot.add_cog(EventCog(bot))
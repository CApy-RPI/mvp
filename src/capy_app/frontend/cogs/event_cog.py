# Standard library imports
import re
import logging
from datetime import datetime, timezone
import pytz

# Third-party imports
import discord
from discord.ext import commands

# Local imports
from backend.db.database import Database as db
from backend.db.documents.user import User
from backend.db.documents.event import Event
from backend.db.documents.guild import Guild

class EventCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = logging.getLogger(f"discord.cog.{self.__class__.__name__.lower()}")
        self.allowed_reactions = ["✅", "❌", "❔"]
        self.logger.info("Event cog initialized.")

    def now(self):
        """Returns current time in UTC."""
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    def format_time(self, time_str: str) -> str:
        """Formats time string to standard format."""
        try:
            dt = datetime.strptime(time_str, "%m/%d/%y %I:%M %p")
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            try:
                dt = datetime.strptime(time_str, "%m/%d/%y %I:%M %p %Z")
                return dt.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                return time_str

    def get_timezone(self, time_str: str) -> str:
        """Extracts timezone from time string, defaults to 'EDT'."""
        parts = time_str.split()
        if len(parts) > 2 and parts[-1] in pytz.all_timezones:
            return parts[-1]
        return 'EDT'

    def localize_datetime(self, time_str: str, timezone_str: str) -> str:
        """Converts datetime to specified timezone."""
        try:
            dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
            timezone = pytz.timezone(timezone_str)
            localized_dt = timezone.localize(dt)
            return localized_dt.strftime("%Y-%m-%d %I:%M %p %Z")
        except (ValueError, pytz.exceptions.UnknownTimeZoneError):
            return time_str

    @commands.group(name="events", invoke_without_command=True, help="Event commands.")
    async def events(self, ctx):
        """Lists all guild events or shows available commands if no subcommand is given."""
        if ctx.invoked_subcommand is None:
            self.logger.info(f"User {ctx.author} requested the list of events.")
            guild = db.get_document(Guild, ctx.guild.id)
            guild_events = []
            
            if guild and hasattr(guild, 'events'):
                for event_id in guild.events[:10]:
                    event = db.get_document(Event, event_id)
                    if event:
                        guild_events.append(event)

            if not guild_events:
                self.logger.info(f"No events found for guild {ctx.guild.id}.")
                await self.send_no_events_embed(ctx)
                return

            self.logger.info(f"Found {len(guild_events)} events for guild {ctx.guild.id}.")
            embed = self.create_events_embed(guild_events)
            await ctx.send(embed=embed)

    def send_no_events_embed(self, ctx):
        """Creates an embed for when no events are found."""
        embed = discord.Embed(
            title="No Events Found",
            description="No events found.",
            color=discord.Color.red(),
        )
        return ctx.send(embed=embed)
    def create_events_embed(self, guild_events):
        """Creates an embed with the list of upcoming events."""
        embed = discord.Embed(
            title="Upcoming Events",
            color=discord.Color.green(),
        )

        for event in guild_events:
            event_details = (
                f"{self.localize_datetime(event.datetime, event.timezone)} \n"
                f"Event ID: {event.id}"
            )
            embed.add_field(name=event.name, value=event_details, inline=False)

        self.logger.info(f"Created events embed with {len(guild_events)} events.")
        return embed

    @events.command(name="add", help="Add a new event.")
    async def add_event(self, ctx):
        """Guides the user through creating a new event."""
        self.logger.info(f"User {ctx.author} is adding a new event.")

        # Collect event details
        name = await self.ask_event_name(ctx)
        if name is None:
            return
            
        event_description = await self.ask_event_description(ctx)
        if event_description is None:
            return
            
        date = await self.ask_event_date(ctx)
        if date is None:
            return
            
        time = await self.ask_event_time(ctx)
        if time is None:
            return
            
        location = await self.ask_event_location(ctx)
        if location is None:
            return

        # Process and save event
        event_timezone = self.get_timezone(time)
        time_str = self.format_time(f"{date} {time}")
        new_event_id = int(datetime.now(timezone.utc).timestamp() * 1000)

        # Create new event
        new_event = Event(
            _id=new_event_id,
            name=name,
            description=event_description,
            datetime=time_str,
            location=location,
            timezone=event_timezone,
            guild_id=ctx.guild.id,
            reactions={"yes": 0, "no": 0, "maybe": 0},
            users=[]
        )
        db.add_document(new_event)

        # Update guild
        guild = db.get_document(Guild, ctx.guild.id)
        if not guild:
            guild = Guild(_id=ctx.guild.id, events=[])
            db.add_document(guild)
        
        if not hasattr(guild, 'events'):
            guild.events = []
        
        guild.events.append(new_event_id)
        db.update_document(guild)

        # Send confirmation
        embed = self.create_confirmation_embed(
            name,
            event_description,
            self.localize_datetime(time_str, event_timezone),
            location,
            new_event_id,
        )
        await ctx.send(embed=embed)
        self.logger.info(f"Event '{name}' added with ID {new_event_id}.")

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

# Setup function to load the cog
async def setup(bot: commands.Bot):
    await bot.add_cog(EventCog(bot))
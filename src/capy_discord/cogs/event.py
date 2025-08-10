import re
import discord
from datetime import datetime, timezone
from discord.ext import commands
from modules.timestamp import now, format_time, get_timezone, localize_datetime
from discord import RawReactionActionEvent


class Events(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.logger.info("Event cog initialized.")
        self.allowed_reactions = ["✅", "❌", "❔"]

    def is_event_passed(self, event_datetime_str, event_timezone_str=None):
        """
        Check if an event has passed based on its datetime and timezone.
        
        Args:
            event_datetime_str (str): The event datetime string
            event_timezone_str (str, optional): The event timezone string
            
        Returns:
            bool: True if the event has passed, False otherwise
        """
        try:
            # Parse the event datetime - this might need adjustment based on actual format
            if event_timezone_str:
                # If timezone info is available, use it
                event_dt = localize_datetime(event_datetime_str, event_timezone_str)
            else:
                # Default timezone handling
                event_dt = datetime.fromisoformat(event_datetime_str.replace('Z', '+00:00'))
            
            # Compare with current time
            current_time = datetime.now(timezone.utc)
            return event_dt < current_time
        except (ValueError, TypeError, AttributeError):
            # If we can't parse the datetime, assume it's not passed
            return False

    @commands.group(name="events", help="Access/Modify Event data.")
    async def events(self, ctx):
        """
        Lists all guild events (including passed events)
        """

        if ctx.invoked_subcommand is None:
            self.bot.logger.info(f"User {ctx.author} requested the list of events.")
            
            # Get ALL events, including passed ones
            # First try to get current/future events
            guild_events = []
            try:
                guild_events = self.bot.db.get_paginated_linked_data(
                    "event", self.bot.db.get_data("guild", ctx.guild.id), 1, 10
                )
            except AttributeError:
                # If the method doesn't exist, try alternative approach
                try:
                    guild_data = self.bot.db.get_data("guild", ctx.guild.id)
                    if guild_data and hasattr(guild_data, 'get_value'):
                        event_ids = guild_data.get_value("event") or []
                        guild_events = []
                        for event_id in event_ids:
                            event_data = self.bot.db.get_data("event", event_id)
                            if event_data:
                                guild_events.append(event_data)
                except:
                    pass
            
            # Also try to get deleted/old events if there's a method for it
            try:
                # Try to get deleted events (which might include old events)
                old_events = self.bot.db.get_paginated_linked_data(
                    "event", self.bot.db.get_data("guild", ctx.guild.id), 1, 10, deleted=True
                )
                if old_events:
                    guild_events.extend(old_events)
            except:
                pass

            if not guild_events:
                self.bot.logger.info(f"No events found for guild {ctx.guild.id}.")
                await self.send_no_events_embed(ctx)
                return

            self.bot.logger.info(
                f"Found {len(guild_events)} events for guild {ctx.guild.id}."
            )
            embed = self.create_events_embed(guild_events)
            await ctx.send(embed=embed)

    @events.command(name="myevents", help="Get events you are registered for.")
    async def my_events(self, ctx):
        """Handles output for the command to get events the user is registered for."""
        self.bot.logger.info(f"User {ctx.author.id} requested their registered events.")

        # Get ALL user events, including passed ones
        user_events = []
        try:
            user_events = self.bot.db.get_paginated_linked_data(
                "event", self.bot.db.get_data("user", ctx.author.id), 1, 10
            )
        except AttributeError:
            # If the method doesn't exist, try alternative approach
            try:
                user_data = self.bot.db.get_data("user", ctx.author.id)
                if user_data and hasattr(user_data, 'get_value'):
                    event_ids = user_data.get_value("event") or []
                    user_events = []
                    for event_id in event_ids:
                        event_data = self.bot.db.get_data("event", event_id)
                        if event_data:
                            user_events.append(event_data)
            except:
                pass
        
        # Also try to get old/deleted events
        try:
            old_user_events = self.bot.db.get_paginated_linked_data(
                "event", self.bot.db.get_data("user", ctx.author.id), 1, 10, deleted=True
            )
            if old_user_events:
                user_events.extend(old_user_events)
        except:
            pass

        if not user_events:
            await self.send_no_events_embed(ctx)
            self.bot.logger.info(f"User {ctx.author.id} has no registered events.")
            return

        await ctx.author.send(embed=self.create_events_embed(user_events))
        self.bot.logger.info(f"Sent registered events to user {ctx.author.id}.")

    @events.command(
        name="show",
        help="Show details of a specific event. Usage: !event show [event_id]",
    )
    async def show_event(self, ctx, event_id: int):
        """Displays the details of a specific event by its ID (including passed events)."""
        self.bot.logger.info(
            f"User {ctx.author} requested details for event ID: {event_id}."
        )

        event_data = self.bot.db.get_data("event", event_id)
        
        # If not found in active events, try to find in deleted/old events
        if not event_data:
            try:
                # Try to get deleted events that might include old events
                deleted_events = self.bot.db.get_paginated_data("event", 1, 100, deleted=True)
                for deleted_event in deleted_events:
                    if deleted_event.get_value("id") == event_id:
                        event_data = deleted_event
                        break
            except:
                pass

        if not event_data:
            await ctx.send(f"No event found with ID: {event_id}.")
            return

        # Check if event has passed
        event_datetime = event_data.get_value("datetime")
        event_timezone = event_data.get_value("timezone")
        is_passed = self.is_event_passed(event_datetime, event_timezone)

        embed = self.create_event_embed(
            name=event_data.get_value("name"),
            event_description=event_data.get_value("description"),
            time_str=event_data.get_value("datetime"),
            location=event_data.get_value("location"),
            event_id=event_data.get_value("id"),
            is_passed=is_passed,
            timezone=event_timezone
        )
        await ctx.send(embed=embed)

    @events.command(
        name="edit",
        help="Edit an existing event. Usage: !event edit [event_id]",
    )
    async def edit_event(self, ctx, event_id: int):
        """Edit an existing event by its ID (including passed events)."""
        self.bot.logger.info(
            f"User {ctx.author} is editing event ID: {event_id}."
        )

        event_data = self.bot.db.get_data("event", event_id)
        
        # If not found in active events, try to find in deleted/old events
        if not event_data:
            try:
                # Try to get deleted events that might include old events
                deleted_events = self.bot.db.get_paginated_data("event", 1, 100, deleted=True)
                for deleted_event in deleted_events:
                    if deleted_event.get_value("id") == event_id:
                        event_data = deleted_event
                        break
            except:
                pass

        if not event_data:
            await ctx.send(f"No event found with ID: {event_id}.")
            return

        # Check if event has passed
        event_datetime = event_data.get_value("datetime")
        event_timezone = event_data.get_value("timezone")
        is_passed = self.is_event_passed(event_datetime, event_timezone)

        # Show current event details
        current_embed = self.create_event_embed(
            name=event_data.get_value("name"),
            event_description=event_data.get_value("description"),
            time_str=event_data.get_value("datetime"),
            location=event_data.get_value("location"),
            event_id=event_data.get_value("id"),
            is_passed=is_passed,
            timezone=event_timezone
        )
        current_embed.title = "Current Event Details"
        await ctx.send(embed=current_embed)

        if is_passed:
            await ctx.send("⚠️ **Warning**: This event has already passed. You can still edit it, but consider if changes are necessary.")

        # Get new event details
        await ctx.send("Let's edit this event. Press Enter to keep current values or type new ones:")

        # Edit name
        await ctx.send(f"Current name: **{event_data.get_value('name')}**\nEnter new name (or press Enter to keep current):")
        name_response = await self.bot.wait_for("message", check=lambda m: m.author == ctx.author)
        new_name = name_response.content.strip() if name_response.content.strip() else event_data.get_value('name')

        # Edit description
        await ctx.send(f"Current description: **{event_data.get_value('description')}**\nEnter new description (or press Enter to keep current):")
        desc_response = await self.bot.wait_for("message", check=lambda m: m.author == ctx.author)
        new_description = desc_response.content.strip() if desc_response.content.strip() else event_data.get_value('description')

        # Edit location
        await ctx.send(f"Current location: **{event_data.get_value('location')}**\nEnter new location (or press Enter to keep current):")
        location_response = await self.bot.wait_for("message", check=lambda m: m.author == ctx.author)
        new_location = location_response.content.strip() if location_response.content.strip() else event_data.get_value('location')

        # For date/time, we'll ask if they want to change it
        await ctx.send(f"Current date/time: **{event_data.get_value('datetime')}**\nDo you want to change the date/time? (yes/no):")
        datetime_change_response = await self.bot.wait_for("message", check=lambda m: m.author == ctx.author)
        
        new_datetime = event_data.get_value('datetime')
        new_timezone = event_data.get_value('timezone')
        
        if datetime_change_response.content.lower().startswith('y'):
            date = await self.ask_for_event_date(ctx)
            time = await self.ask_for_event_time(ctx)
            new_timezone = get_timezone(time)
            new_datetime = format_time(f"{date} {time}")

        # Update the event data
        event_data.set_value("name", new_name)
        event_data.set_value("description", new_description)
        event_data.set_value("location", new_location)
        event_data.set_value("datetime", new_datetime)
        event_data.set_value("timezone", new_timezone)

        # Save the updated event
        self.bot.db.upsert_data(event_data)

        # Check if the updated event is now passed or not
        updated_is_passed = self.is_event_passed(new_datetime, new_timezone)

        # Show updated event details
        updated_embed = self.create_event_embed(
            name=new_name,
            event_description=new_description,
            time_str=new_datetime,
            location=new_location,
            event_id=event_id,
            is_passed=updated_is_passed,
            timezone=new_timezone
        )
        updated_embed.title = "Event Updated Successfully!"
        updated_embed.description = f"The event '{new_name}' has been updated."
        
        await ctx.send(embed=updated_embed)
        self.bot.logger.info(f"Event ID {event_id} updated successfully by {ctx.author}.")

    async def send_no_events_embed(self, ctx):
        """
        Sends an embed message when there are no upcoming events.
        """
        self.bot.logger.info(f"No events for guild {ctx.guild.id}.")
        embed = discord.Embed(
            title="No Events Found",
            description="There are no events scheduled at the moment.",
            color=discord.Color.red(),
        )
        await ctx.send(embed=embed)

    def create_events_embed(self, guild_events):
        """
        Creates an embed with the list of events (including passed events with labels).
        """
        embed = discord.Embed(
            title="Events",
            color=discord.Color.green(),
        )

        current_events = []
        passed_events = []

        for event in guild_events:
            event_datetime = event.get_value('datetime')
            event_timezone = event.get_value('timezone')
            
            # Check if event has passed
            is_passed = self.is_event_passed(event_datetime, event_timezone)
            
            if is_passed:
                passed_events.append(event)
            else:
                current_events.append(event)

        # Add current/upcoming events first
        if current_events:
            for event in current_events:
                event_details = f"{localize_datetime(event.get_value('datetime'), event.get_value('timezone'))} \nEvent ID: {event.get_value('id')}"
                embed.add_field(
                    name=event.get_value("name"), value=event_details, inline=False
                )

        # Add passed events with PASSED label
        if passed_events:
            if current_events:
                embed.add_field(name="\u200b", value="**— PASSED EVENTS —**", inline=False)
            
            for event in passed_events:
                event_details = f"🚫 **PASSED** - {localize_datetime(event.get_value('datetime'), event.get_value('timezone'))} \nEvent ID: {event.get_value('id')}"
                embed.add_field(
                    name=f"🕒 {event.get_value('name')}", value=event_details, inline=False
                )

        total_events = len(current_events) + len(passed_events)
        if current_events and passed_events:
            embed.title = f"Events ({len(current_events)} upcoming, {len(passed_events)} passed)"
        elif passed_events and not current_events:
            embed.title = f"Events ({len(passed_events)} passed)"
        elif current_events:
            embed.title = f"Upcoming Events ({len(current_events)})"

        self.bot.logger.info(f"Created events embed with {total_events} events.")
        return embed

    @events.command(name="add", help="Add a new event. Usage: !event add")
    async def add_event(self, ctx):
        """Creates event, adds to guild events list, prints confirmation embed"""
        self.bot.logger.info(f"User {ctx.author} is adding a new event.")

        name = await self.ask_for_event_name(ctx)
        event_description = await self.ask_for_event_description(ctx)
        date = await self.ask_for_event_date(ctx)
        time = await self.ask_for_event_time(ctx)
        location = await self.ask_for_event_location(ctx)
        event_timezone = get_timezone(time)

        time_str = format_time(f"{date} {time}")

        guild_data = self.bot.db.get_data("guild", ctx.guild.id)
        new_event_id = int(datetime.now(timezone.utc).timestamp() * 1000)
        new_event_data = self.create_event_data(
            new_event_id,
            name,
            event_description,
            time_str,
            location,
            event_timezone,
            ctx.guild.id,
        )

        self.bot.db.upsert_data(new_event_data)
        guild_data.append_value("event", new_event_id)
        self.bot.db.upsert_data(guild_data)

        embed = self.create_confirmation_embed(
            name,
            event_description,
            localize_datetime(time_str, new_event_data.get_value("timezone")),
            location,
            new_event_id,
        )
        await ctx.send(embed=embed)
        self.bot.logger.info(f"Event '{name}' added with ID {new_event_id}.")

    def create_confirmation_embed(
        self, name, event_description, datetime_str, location, event_id
    ):
        """Creates a confirmation embed for the added event."""
        embed = self.create_event_embed(
            name, event_description, datetime_str, location, event_id,
            is_passed=False,  # New events are never passed
            timezone=None
        )
        embed.title = "Event Added Successfully!"
        embed.description = f"The event '{name}' has been added to the calendar."
        return embed

    async def ask_for_event_name(self, ctx):
        """Asks for the event name and returns it."""
        await ctx.send("Please enter the event name:")
        name_message = await self.bot.wait_for(
            "message", check=lambda m: m.author == ctx.author
        )
        self.bot.logger.info(f"Event name received: {name_message.content}")
        return name_message.content

    async def ask_for_event_description(self, ctx):
        """Asks for the event description and returns it."""
        await ctx.send("Please enter the event description:")
        description_message = await self.bot.wait_for(
            "message", check=lambda m: m.author == ctx.author
        )
        self.bot.logger.info(
            f"Event description received: {description_message.content}"
        )
        return description_message.content

    async def ask_for_event_date(self, ctx):
        """Asks for the event date in mm/dd/yy format and returns it."""
        date_pattern = re.compile(r"^(0[1-9]|1[0-2])\/(0[1-9]|[12][0-9]|3[01])\/\d{2}$")

        while True:
            await ctx.send(
                "Please enter the event date in mm/dd/yy format (e.g., 12/31/24):"
            )
            date_message = await self.bot.wait_for(
                "message", check=lambda m: m.author == ctx.author
            )
            date_input = date_message.content.strip()

            # Check if the input matches the mm/dd/yy format
            if date_pattern.match(date_input):
                self.bot.logger.info(f"Event date received: {date_input}")
                return date_input
            else:
                await ctx.send(
                    "Invalid date format. Please enter the date in mm/dd/yy format."
                )

    async def ask_for_event_location(self, ctx):
        """Asks for the event location and returns it."""
        await ctx.send("Please enter the event location:")
        location_message = await self.bot.wait_for(
            "message", check=lambda m: m.author == ctx.author
        )
        self.bot.logger.info(f"Event location received: {location_message.content}")
        return location_message.content

    async def ask_for_event_time(self, ctx):
        """Asks for the event time in 'HH:MM AM/PM Timezone' format and returns it."""
        # Regular expression to match "HH:MM AM/PM" with an optional timezone
        time_pattern = re.compile(r"^(0[1-9]|1[0-2]):[0-5][0-9] (AM|PM)( [A-Z]{2,4})?$")

        while True:
            await ctx.send(
                "Please enter the event time in the format 'HH:MM AM/PM Timezone' (e.g., 12:00 PM PDT). Timezone is optional, defaults to EDT."
            )
            time_message = await self.bot.wait_for(
                "message", check=lambda m: m.author == ctx.author
            )
            time_input = time_message.content.strip()

            # Check if the input matches the required time format
            if time_pattern.match(time_input):
                self.bot.logger.info(f"Event time received: {time_input}")
                return time_input
            else:
                await ctx.send("Invalid time format.")

    def create_event_data(
        self,
        event_id: int,
        name: str,
        description: str,
        time_str: str,
        location: str,
        event_timezone: str,
        guild_id: int,
    ):
        """Creates a new event data object."""
        new_event_data = self.bot.db.create_data("event", event_id)

        new_event_data.set_value("name", name)  # Should be a string
        new_event_data.set_value("description", description)
        new_event_data.set_value("datetime", time_str)  # string
        new_event_data.set_value("location", location)  # string
        new_event_data.set_value("timezone", event_timezone)  # string
        new_event_data.set_value("guild_id", guild_id)  # int

        self.bot.logger.info(f"Event data created for event ID {event_id}.")
        return new_event_data

    def create_event_embed(
        self,
        name: str,
        event_description: str,
        time_str: str,
        location: str,
        event_id: int,
        is_passed: bool = False,
        timezone: str = None,
    ):
        """Creates an embed to display event details with status indicators."""
        # Add passed indicator to title if event has passed
        title = f"🕒 {name}" if is_passed else name
        
        embed = discord.Embed(
            title=title,
            description=event_description,
            color=discord.Color.red() if is_passed else discord.Color.blue(),
        )
        
        # Format the time display
        if is_passed:
            time_display = f"🚫 **PASSED** - {time_str}"
        else:
            time_display = time_str
            
        embed.add_field(name="Date/Time", value=time_display, inline=True)
        embed.add_field(name="Location", value=location, inline=True)
        embed.add_field(name="Event ID", value=str(event_id), inline=False)
        
        if is_passed:
            embed.add_field(name="Status", value="🚫 **PASSED**", inline=True)
        elif timezone:
            embed.add_field(name="Timezone", value=timezone, inline=True)
        return embed

    @events.command(
        name="delete",
        help="Deletes a specific event given id. Usage: !event delete [id]",
    )
    async def delete_event(self, ctx, id: int):
        """
        Deletes an event given event id
        """
        self.bot.logger.info(
            f"User {ctx.author} is attempting to delete event ID {id}."
        )
        event_data = self.bot.db.get_data("event", id)

        if event_data:
            self.bot.db.soft_delete("event", id)
            await ctx.send(embed=self.create_event_deletion_embed(id))
            self.bot.logger.info(f"Event ID {id} deleted successfully.")
        else:
            await ctx.send(
                f"Event with ID '{id}' has already been deleted or does not exist."
            )
            self.bot.logger.warning(f"Attempted to delete non-existent event ID {id}.")

    def create_event_deletion_embed(self, id: int):
        """Creates an embed to confirm the event was deleted."""
        embed = discord.Embed(
            title="Event Deleted",
            description=f"Event with ID '{id}' has been deleted successfully!",
            color=discord.Color.red(),
        )
        embed.add_field(name="Event ID", value=str(id), inline=False)
        return embed

    def create_clear_events_embed(self):
        """Creates an embed to confirm all events have been cleared."""
        embed = discord.Embed(
            title="Events Cleared",
            description="All events have been successfully cleared.",
            color=discord.Color.orange(),
        )
        return embed

    @events.command(
        name="clear", help="Clears all upcoming events. Usage: !event clear"
    )
    async def clear_events(self, ctx):
        """
        Deletes all future guild events
        """
        self.bot.logger.info(
            f"User {ctx.author} is clearing all events for guild {ctx.guild.id}."
        )
        self.bot.logger.info(
            f"User {ctx.author} is clearing all events for guild {ctx.guild.id}."
        )

        # Soft delete all future events associated with this guild
        self.bot.db.bulk_soft_delete_cutoff("event", now())
        self.bot.db.bulk_soft_delete_cutoff("event", now())

        # Create an embed to confirm the events have been cleared
        embed = self.create_clear_events_embed()

        # Send the embed confirmation message
        await ctx.send(embed=embed)
        self.bot.logger.info("All events cleared successfully.")

    #! RESTRICT REGULAR MEMBERS FROM USING THIS FEATURE
    # Shows admin all the users who are registered for a specific event
    @commands.command(
        name="attendance",
        help="Shows attendance for a specific event (Admin Only). Usage: !attendance [event id]",
    )
    async def show_event_attendance(self, ctx, message_id: int):
        """ "Displays attendance for a specific event"""
        guild_data = self.bot.db.get_data("guild", ctx.guild.id)
        event = next(
            (
                event
                for event in guild_data.get_value("event")
                if event["id"] == event_id
            ),
            None,
        )

        if not event or not event.get("user"):
            await ctx.send("Event not found")
            return

        attendees = [self.bot.get_user(user_id).name for user_id in event["user"]]
        attendee_list = "\n".join(attendees) if attendees else "No attendees yet."

        embed = discord.Embed(
            title="Event Attendance",
            description=f"**Event ID:** {event_id}",
            color=discord.Color.green(),
        )
        embed.add_field(name="Attendees", value=attendee_list, inline=False)

        await ctx.send(embed=embed)

    @commands.command(
        name="announce",
        help="Announces an event in the announcements channel. Usage: !announce [event id]",
    )
    async def announce(self, ctx, event_id: int):
        """
        Announces an event in the announcements channel
        """

        # Get event data from the database
        event = self.bot.db.get_data("event", event_id)

        if not event:
            await ctx.send("ERROR: Event not found.")
            return

        # Find the #announcements channel
        announcement_channel = discord.utils.get(
            ctx.guild.text_channels, name="announcements"
        )

        # Create it if it doesn't exist
        if announcement_channel is None:
            try:
                # Create the #announcements channel with permissions allowing only the bot to send messages
                announcement_channel = await ctx.guild.create_text_channel(
                    "announcements"
                )
                await announcement_channel.set_permissions(
                    ctx.guild.default_role, send_messages=False
                )
                await announcement_channel.set_permissions(
                    ctx.guild.me, send_messages=True
                )
            except discord.Forbidden:
                await ctx.send("ERROR: I do not have permission to create channels.")
                return
        else:
            # If the channel already exists, ensure permissions are set correctly
            await announcement_channel.set_permissions(
                ctx.guild.default_role, send_messages=False
            )
            await announcement_channel.set_permissions(ctx.guild.me, send_messages=True)

        # Create the embed for announcements
        embed = discord.Embed(
            title="Event Announcement",
            description=f"**Event:** {event.get_value('name')}\n**Date/Time:** {event.get_value('datetime')}\n**Location:** {event.get_value('location')}\n\nReact with ✅ to attend, ❌ to decline, or ❔ for maybe.",
            color=discord.Color.purple(),
        )

        try:
            # Send announcement to the channel and add reactions for attendance
            message = await announcement_channel.send(embed=embed)
            await message.add_reaction("✅")  # Add reaction for attendance
            await message.add_reaction("❌")  # Add reaction for decline
            await message.add_reaction("❔")  # Add reaction for maybe
            event.set_value("message_id", message.id)

            # Update event data
            self.bot.db.upsert_data(event)

            await ctx.send(f"Event announced in #{announcement_channel.name}!")

            self.bot.logger.info(
                f"Event announced successfully in #{announcement_channel.name} with message ID {message.id}. NUM 7"
            )  #! Debug statement 7
        except discord.Forbidden:
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
            print(f"Updated Reactions: {reactions}")

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
                print(f"Updated Reactions: {reactions}")

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


# Setup function to load the cog
async def setup(bot):
    await bot.add_cog(Events(bot))

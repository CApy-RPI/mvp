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

    def update_event_status(self, event_data):
        """Update event status based on current time."""
        event_datetime = event_data.get_value('datetime')
        current_status = event_data.get_value('status') or 'upcoming'
        
        if isinstance(event_datetime, str):
            from datetime import datetime
            try:
                event_dt = datetime.fromisoformat(event_datetime.replace('Z', '+00:00'))
                if event_dt < datetime.now() and current_status != 'passed':
                    event_data.set_value('status', 'passed')
                    self.bot.db.upsert_data(event_data)
                    return True
            except:
                pass
        return False

    @commands.group(name="events", help="Access/Modify Event data.")
    async def events(self, ctx):
        """
        Lists all guild events
        """

        if ctx.invoked_subcommand is None:
            self.bot.logger.info(f"User {ctx.author} requested the list of events.")
            
            # Get all events for this guild
            all_events = self.bot.db.get_paginated_data("event", 1, 100)
            guild_events = [event for event in all_events if event.get_value("guild_id") == ctx.guild.id]

            if not guild_events:
                self.bot.logger.info(f"No events found for guild {ctx.guild.id}.")
                await self.send_no_events_embed(ctx)
                return

            self.bot.logger.info(
                f"Found {len(guild_events)} events for guild {ctx.guild.id}."
            )
            embed = self.create_events_embed(guild_events, include_status=True)
            embed.title = "Guild Events"
            await ctx.send(embed=embed)

    @events.command(name="myevents", help="Get events you are registered for.")
    async def my_events(self, ctx):
        """Handles output for the command to get events the user is registered for."""
        self.bot.logger.info(f"User {ctx.author.id} requested their registered events.")

        # Get user data and their registered events
        user_data = self.bot.db.get_data("user", ctx.author.id)
        if not user_data:
            await ctx.send("You need to create a profile first!")
            return

        user_event_ids = user_data.get_value("events") or []
        
        if not user_event_ids:
            await self.send_no_events_embed(ctx)
            self.bot.logger.info(f"User {ctx.author.id} has no registered events.")
            return

        # Get event details for each registered event
        user_events = []
        for event_id in user_event_ids:
            event_data = self.bot.db.get_data("event", event_id)
            if event_data:
                user_events.append(event_data)

        if not user_events:
            await self.send_no_events_embed(ctx)
            return

        embed = self.create_events_embed(user_events, include_status=True)
        embed.title = "Your Registered Events"
        await ctx.author.send(embed=embed)
        self.bot.logger.info(f"Sent registered events to user {ctx.author.id}.")

    @events.command(
        name="show",
        help="Show details of a specific event. Usage: !event show [event_id]",
    )
    async def show_event(self, ctx, event_id: int):
        """Displays the details of a specific event by its ID."""
        self.bot.logger.info(
            f"User {ctx.author} requested details for event ID: {event_id}."
        )

        event_data = self.bot.db.get_data("event", event_id)

        if not event_data:
            await ctx.send(f"No event found with ID: {event_id}.")
            return

        # Check if event is in the past
        event_status = event_data.get_value('status') or 'upcoming'
        event_datetime = event_data.get_value('datetime')
        
        if isinstance(event_datetime, str):
            from datetime import datetime
            try:
                event_dt = datetime.fromisoformat(event_datetime.replace('Z', '+00:00'))
                if event_dt < datetime.now():
                    event_status = 'passed'
            except:
                pass

        embed = self.create_event_embed(
            name=event_data.get_value("name"),
            event_description=event_data.get_value("description"),
            time_str=event_data.get_value("datetime"),
            location=event_data.get_value("location"),
            event_id=event_data.get_value("id"),
            status=event_status,
            reactions=event_data.get_value("reactions")
        )
        await ctx.send(embed=embed)

    async def send_no_events_embed(self, ctx):
        """
        Sends an embed message when there are no upcoming events.
        """
        self.bot.logger.info(f"No upcoming events for guild {ctx.guild.id}.")
        embed = discord.Embed(
            title="No Upcoming Events",
            description="There are no events scheduled at the moment.",
            color=discord.Color.red(),
        )
        await ctx.send(embed=embed)

    def create_events_embed(self, guild_events, include_status=False):
        """
        Creates an embed with the list of events.
        """
        embed = discord.Embed(
            title="Events",
            color=discord.Color.green(),
        )

        upcoming_events = []
        past_events = []

        for event in guild_events:
            event_datetime = event.get_value('datetime')
            event_status = event.get_value('status') or 'upcoming'
            
            # Check if event is in the past
            if isinstance(event_datetime, str):
                from datetime import datetime
                try:
                    event_dt = datetime.fromisoformat(event_datetime.replace('Z', '+00:00'))
                    if event_dt < datetime.now():
                        event_status = 'passed'
                except:
                    pass
            
            event_details = f"{localize_datetime(event.get_value('datetime'), event.get_value('timezone'))} \nEvent ID: {event.get_value('id')}"
            
            if include_status and event_status == 'passed':
                event_details += f"\n**Status:** PASSED"
                past_events.append((event.get_value("name"), event_details))
            else:
                if event_status == 'upcoming':
                    upcoming_events.append((event.get_value("name"), event_details))

        # Add upcoming events first
        for name, details in upcoming_events:
            embed.add_field(name=name, value=details, inline=False)
            
        # Add past events if requested
        if include_status and past_events:
            embed.add_field(name="━━━━━━ Past Events ━━━━━━", value="", inline=False)
            for name, details in past_events:
                embed.add_field(name=name, value=details, inline=False)

        if not upcoming_events and not past_events:
            embed.description = "No events found."

        self.bot.logger.info(f"Created events embed with {len(guild_events)} events.")
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
            name, event_description, datetime_str, location, event_id, "upcoming"
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
        new_event_data.set_value("reactions", {"yes": 0, "no": 0, "maybe": 0})  # Initialize reactions
        new_event_data.set_value("user_responses", [])  # Initialize user responses
        new_event_data.set_value("status", "upcoming")  # Initialize status
        new_event_data.set_value("users", [])  # Initialize users list

        self.bot.logger.info(f"Event data created for event ID {event_id}.")
        return new_event_data

    def create_event_embed(
        self,
        name: str,
        event_description: str,
        time_str: str,
        location: str,
        event_id: int,
        status: str = "upcoming",
        reactions: dict = None,
    ):
        """Creates an embed to display event details."""
        color = discord.Color.blue()
        if status == "passed":
            color = discord.Color.orange()
        
        embed = discord.Embed(
            title=name,
            description=event_description,
            color=color,
        )
        embed.add_field(name="Date/Time", value=time_str, inline=True)
        embed.add_field(name="Location", value=location, inline=True)
        embed.add_field(name="Event ID", value=str(event_id), inline=False)
        
        if status == "passed":
            embed.add_field(name="Status", value="**PASSED**", inline=True)
        
        if reactions:
            reaction_text = f"✅ {reactions.get('yes', 0)} | ❌ {reactions.get('no', 0)} | ❔ {reactions.get('maybe', 0)}"
            embed.add_field(name="Reactions", value=reaction_text, inline=False)
        
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

    async def handle_user_reaction(self, user_id, message_id, response):
        """
        Unified method to handle user reactions (yes/no/maybe) to events.
        Ensures only one reaction per user and updates both event and user data.
        """
        # Get user data
        user_data = self.bot.db.get_data("user", user_id)
        if not user_data:
            self.bot.logger.warning(f"User ID {user_id} not found.")
            return

        # Find the event associated with this message
        event_data = None
        event_id = None
        all_event_data = self.bot.db.get_paginated_data("event", 1, 100)
        
        for row in all_event_data:
            if row.get_value("message_id") == message_id:
                event_data = row
                event_id = row.get_value("id")
                break

        if not event_data:
            self.bot.logger.warning(f"Event not found for message ID {message_id}.")
            return

        # Get current reactions and user responses
        reactions = event_data.get_value("reactions") or {"yes": 0, "no": 0, "maybe": 0}
        user_responses = event_data.get_value("user_responses") or []
        
        # Find existing user response
        existing_response = None
        for i, user_response in enumerate(user_responses):
            if user_response.get("user_id") == user_id:
                existing_response = i
                break

        # Update reaction counts
        if existing_response is not None:
            # Remove old response count
            old_response = user_responses[existing_response].get("response")
            if old_response in reactions:
                reactions[old_response] = max(0, reactions[old_response] - 1)
            # Update the response
            user_responses[existing_response] = {"user_id": user_id, "response": response}
        else:
            # Add new response
            user_responses.append({"user_id": user_id, "response": response})

        # Add new response count
        reactions[response] += 1

        # Update event data
        event_data.set_value("reactions", reactions)
        event_data.set_value("user_responses", user_responses)

        # Update user events list
        user_events = user_data.get_value("events") or []
        if response == "yes" and event_id not in user_events:
            user_events.append(event_id)
            user_data.set_value("events", user_events)
        elif response != "yes" and event_id in user_events:
            user_events.remove(event_id)
            user_data.set_value("events", user_events)

        # Update event users list
        event_users = event_data.get_value("users") or []
        if response == "yes" and user_id not in event_users:
            event_users.append(user_id)
            event_data.set_value("users", event_users)
        elif response != "yes" and user_id in event_users:
            event_users.remove(user_id)
            event_data.set_value("users", event_users)

        # Save updated data
        self.bot.db.upsert_data(event_data)
        self.bot.db.upsert_data(user_data)
        
        self.bot.logger.info(f"User {user_id} reacted '{response}' to event {event_id}.")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        """
        Listens for reaction to event announcements and calls the appropriate function.

        Handle adding a reaction to limit users to only one option.
        """

        # Ensure this is not the bot's reaction
        if payload.user_id == self.bot.user.id:
            return

        # Only handle allowed reactions
        if payload.emoji.name not in self.allowed_reactions:
            return

        # Fetch the message where the reaction was added
        channel = self.bot.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)

        # Find the event associated with this message
        event_data = None
        all_event_data = self.bot.db.get_paginated_data("event", 1, 100)
        for row in all_event_data:
            if row.get_value("message_id") == payload.message_id:
                event_data = row
                break
        
        if not event_data:
            return

        # Remove user's previous reactions on this message
        user = self.bot.get_user(payload.user_id)
        if user:
            for reaction in message.reactions:
                if reaction.emoji != payload.emoji.name and user in [u async for u in reaction.users()]:
                    await reaction.remove(user)

        # Handle the reaction
        if payload.emoji.name == "✅":
            await self.handle_user_reaction(payload.user_id, payload.message_id, "yes")
        elif payload.emoji.name == "❌":
            await self.handle_user_reaction(payload.user_id, payload.message_id, "no")
        elif payload.emoji.name == "❔":
            await self.handle_user_reaction(payload.user_id, payload.message_id, "maybe")

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        """
        Handle reaction removal - removes user's response completely.
        """
        # Ensure this is not the bot's reaction
        if payload.user_id == self.bot.user.id:
            return

        # Only handle allowed reactions
        if payload.emoji.name not in self.allowed_reactions:
            return

        # Find the event associated with this message
        event_data = None
        event_id = None
        all_event_data = self.bot.db.get_paginated_data("event", 1, 100)
        
        for row in all_event_data:
            if row.get_value("message_id") == payload.message_id:
                event_data = row
                event_id = row.get_value("id")
                break
        
        if not event_data:
            return

        # Get user data
        user_data = self.bot.db.get_data("user", payload.user_id)
        if not user_data:
            return

        # Remove user's response
        await self.remove_user_reaction(payload.user_id, payload.message_id)

    async def remove_user_reaction(self, user_id, message_id):
        """
        Remove a user's reaction completely from an event.
        """
        # Find the event associated with this message
        event_data = None
        event_id = None
        all_event_data = self.bot.db.get_paginated_data("event", 1, 100)
        
        for row in all_event_data:
            if row.get_value("message_id") == message_id:
                event_data = row
                event_id = row.get_value("id")
                break

        if not event_data:
            return

        # Get user data
        user_data = self.bot.db.get_data("user", user_id)
        if not user_data:
            return

        # Get current reactions and user responses
        reactions = event_data.get_value("reactions") or {"yes": 0, "no": 0, "maybe": 0}
        user_responses = event_data.get_value("user_responses") or []
        
        # Find and remove user's response
        for i, user_response in enumerate(user_responses):
            if user_response.get("user_id") == user_id:
                old_response = user_response.get("response")
                # Remove response count
                if old_response in reactions:
                    reactions[old_response] = max(0, reactions[old_response] - 1)
                # Remove user response
                user_responses.pop(i)
                break

        # Update event data
        event_data.set_value("reactions", reactions)
        event_data.set_value("user_responses", user_responses)

        # Remove from user events list if they were attending
        user_events = user_data.get_value("events") or []
        if event_id in user_events:
            user_events.remove(event_id)
            user_data.set_value("events", user_events)

        # Remove from event users list
        event_users = event_data.get_value("users") or []
        if user_id in event_users:
            event_users.remove(user_id)
            event_data.set_value("users", event_users)

        # Save updated data
        self.bot.db.upsert_data(event_data)
        self.bot.db.upsert_data(user_data)
        
        self.bot.logger.info(f"Removed user {user_id}'s reaction from event {event_id}.")


# Setup function to load the cog
async def setup(bot):
    await bot.add_cog(Events(bot))

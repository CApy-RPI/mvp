"""Discord bot module for handling discord-related functionality."""

# Standard library imports
import logging
import os
import typing

# Third-party imports
import discord
from discord.ext import commands
from discord.ext.commands import Context
from backend.db.documents.guild import Guild

# Local imports
from backend.db.database import Database as db
from config import settings

class Bot(commands.AutoShardedBot):
    """Main bot class handling Discord events and commands."""

    def __init__(self, **options: typing.Any) -> None:
        """Initialize the Bot instance."""
        super().__init__(
            **options,
        )
        self.logger = logging.getLogger("discord.main")
        self.logger.setLevel(logging.INFO)

    async def on_guild_join(self, guild: discord.Guild) -> None:
        """Handle event when bot joins a new guild.

        Args:
            guild: Discord guild object representing the joined server.
        """
        guild_data = db.get_document(Guild, guild.id)

        if not guild_data:
            guild_data = Guild(_id=guild.id)
            guild_data.save()
            self.logger.info(
                f"Created new guild entry for {guild.name} (ID: {guild.id})"
            )
        else:
            db.sync_document_with_template(guild_data, Guild)
            self.logger.info(
                f"Guild {guild.name} (ID: {guild.id}) already exists and synced"
            )

    async def on_member_join(self, member: discord.Member) -> None:
        """Handle event when a new member joins a guild.

        Args:
            member: Discord member object representing the joined user
        """
        guild_data = db.Database.get_document(db.Guild, member.guild.id)
        if not guild_data:
            guild_data = db.Guild(_id=member.guild.id)
            guild_data.save()
            self.logger.info(
                f"Created new guild entry for {member.guild.name}"
                f" (ID: {member.guild.id})"
            )
        else:
            db.sync_document_with_template(guild_data, db.Guild)

        guild_data.users.append(member.id)
        guild_data.save()
        self.logger.info(
            f"User {member.id} joined guild {member.guild.name}"
            f" (ID: {member.guild.id})"
        )

    async def setup_hook(self) -> None:
        """Load all cog extensions during bot setup."""
        for filename in os.listdir(settings.COG_PATH):
            if not filename.endswith(".py"):
                self.logger.warning(f"Skipping {filename}: Not a Python file")
                continue

            try:
                await self.load_extension(
                    f"{settings.COG_PATH.replace('/', '.')}.{filename[:-3]}"
                )
                self.logger.info(f"Loaded {filename}")
            except Exception as e:
                self.logger.error(f"Failed to load {filename}: {e}")

    async def on_ready(self) -> None:
        """Handle bot ready event and log connection details."""
        if self.user is None:
            return

        self.logger.info(f"Logged in as {self.user.name} - {self.user.id}")
        self.logger.info(
            f"Connected to {len(self.guilds)} guilds "
            f"across {self.shard_count} shards."
        )

    async def on_message(self, message: discord.Message) -> None:
        """Process incoming messages and commands.

        Args:
            message: Discord message object to process
        """
        if message.author.bot:
            return

        await self.process_commands(message)

    async def on_command(self, ctx: Context[typing.Any]) -> None:
        """Handle command processing and restrictions.

        Args:
            ctx: Command context object
        """
        if settings.WHO_DUNNIT:
            await ctx.send(
                f"This bot hosted by {settings.WHO_DUNNIT} is currently in development mode."
            )

        if not settings.DEV_LOCKED_CHANNEL_ID:
            self.logger.info(f"Command executed: {ctx.command} by {ctx.author}")
            return

        if ctx.channel.id == settings.DEV_LOCKED_CHANNEL_ID:
            self.logger.info(f"Command executed: {ctx.command} by {ctx.author}")
            return

        dev_channel = self.get_channel(settings.DEV_LOCKED_CHANNEL_ID)
        if not isinstance(dev_channel, (discord.TextChannel, discord.Thread)):
            await ctx.send("Developer channel not found. Ensure it is set correctly.")
            self.logger.error(
                f"Developer channel {settings.DEV_LOCKED_CHANNEL_ID} not found"
            )
            return

        await ctx.send(
            f"Please use {dev_channel.mention} instead which this session is locked to."
        )
        self.logger.info(
            f"Command from {ctx.author} in disallowed channel {ctx.channel}"
        )

    async def on_command_error(
        self, ctx: Context[typing.Any], error: Exception
    ) -> None:
        """Handle command execution errors.

        Args:
            ctx: Command context object
            error: Exception that occurred during command execution
        """
        self.logger.error(f"{ctx.command}: {error}")
        await ctx.send(f"Failed to execute command: {error}")

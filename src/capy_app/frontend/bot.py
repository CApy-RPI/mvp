"""Discord bot module for handling discord-related functionality."""

# Standard library imports
import logging
import typing
import pathlib

# Third-party imports
import discord
from discord.ext import commands
from discord.ext.commands import Context

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

    async def _load_cogs_recursive(self, path: pathlib.Path, base_package: str) -> None:
        """Recursively load cogs from a directory and its subdirectories.

        Args:
            path: Directory path to search for cogs
            base_package: Base package path for imports
        """
        for item in path.iterdir():
            if (
                item.is_file()
                and item.name.endswith("cog.py")
                and not item.name.startswith("_")
            ):
                # Convert path to module path and load extension
                module_path = (
                    str(item.relative_to(pathlib.Path(settings.COG_PATH)))
                    .replace("\\", ".")
                    .replace("/", ".")[:-3]
                )
                full_module_path = f"{base_package}.{module_path}"
                try:
                    await self.load_extension(full_module_path)
                    self.logger.info(f"Loaded {full_module_path}")
                except Exception as e:
                    self.logger.error(f"Failed to load {full_module_path}: {e}")

            elif item.is_dir() and not item.name.startswith("_"):
                # Recursively explore subdirectories
                await self._load_cogs_recursive(item, f"{base_package}")

    async def setup_hook(self) -> None:
        """Load all cog extensions during bot setup."""
        cog_path = pathlib.Path(settings.COG_PATH)
        await self._load_cogs_recursive(cog_path, settings.COG_PATH.replace("/", "."))
        self.logger.info("Cog extensions loaded")

    async def on_ready(self) -> None:
        """Handle bot ready event and log connection details."""
        if self.user is None:
            return

        if settings.DEBUG_GUILD_ID:
            self.logger.info(f"Connected to debug guild {settings.DEBUG_GUILD_ID}")
            synced = await self.tree.sync(guild=self.get_guild(settings.DEBUG_GUILD_ID))
            self.logger.info(f"Synced {len(synced)} application commands")

        self.logger.info(f"Logged in as {self.user.name} - {self.user.id}")
        self.logger.info(
            f"Connected to {len(self.guilds)} guilds "
            f"across {self.shard_count} shards"
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

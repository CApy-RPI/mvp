"""Discord bot module for handling discord-related functionality."""

import json

# Standard library imports
import logging
import pathlib
import typing
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

# Third-party imports
import discord

# Local imports
from backend.db.database import Database
from discord.ext import commands, tasks
from discord.ext.commands import Context
from frontend.onboarding.onboarding_manager import OnboardingManager

from capy_app.stats import Statistics
from config import settings


class Bot(commands.AutoShardedBot):
    """Main bot class handling Discord events and commands."""

    def __init__(self, **options: typing.Any) -> None:
        """Initialize the Bot instance."""
        super().__init__(
            command_prefix=settings.BOT_COMMAND_PREFIX,
            intents=discord.Intents.all(),
            **options,
        )
        self.logger = logging.getLogger("discord.main")
        self.logger.setLevel(settings.LOG_LEVEL)

        self.tree.error(coro=self._dispatch_slash_command_error)
        self.stats = Statistics()
        self.stat_file = settings.STAT_LOG_FILE

    async def on_member_join(self, member: discord.Member) -> None:
        """Handle event when a new member joins a guild.

        Args:
            member: Discord member object representing the joined user
        """
        guild_data = Database.get_document(Database.Guild, member.guild.id)
        if not guild_data:
            guild_data = Database.Guild(_id=member.guild.id)
            guild_data.save()
            self.logger.info(f"Created new guild entry for {member.guild.name} (ID: {member.guild.id})")
        else:
            Database.sync_document_with_template(guild_data, Database.Guild)

        guild_data.users.append(member.id)
        guild_data.save()
        self.logger.info(f"User {member.id} joined guild {member.guild.name} (ID: {member.guild.id})")

    async def _load_cogs_recursive(self, path: pathlib.Path, base_package: str) -> None:
        """Recursively load cogs from a directory and its subdirectories.

        Args:
            path: Directory path to search for cogs
            base_package: Base package path for imports
        """
        for item in path.iterdir():
            if settings.DEBUG_GUILD_ID is None and item.name.endswith("test_cog.py"):
                continue

            if item.is_file() and item.name.endswith("cog.py") and not item.name.startswith("_"):
                # Convert path to module path and load extension
                module_path = (
                    str(item.relative_to(pathlib.Path(settings.COG_PATH))).replace("\\", ".").replace("/", ".")[:-3]
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

        # Register persistent views (e.g., onboarding DM buttons) after restart
        try:
            OnboardingManager.register_persistent_views(self)
        except Exception as e:
            self.logger.error(f"Failed registering persistent views: {e}")

        # Moved to guild_handler_cog.py
        # if settings.DEBUG_GUILD_ID:
        #     self.logger.info(f"Connected to debug guild {settings.DEBUG_GUILD_ID}")
        #     synced = await self.tree.sync(guild=self.get_guild(settings.DEBUG_GUILD_ID))
        #     self.logger.info(f"Synced {len(synced)} application commands")

        self.logger.info(f"Logged in as {self.user.name} - {self.user.id}")
        self.logger.info(f"Connected to {len(self.guilds)} guilds across {self.shard_count} shards")

        # Start tasks
        self.output_stats.start()

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
            await ctx.send(f"This bot hosted by {settings.WHO_DUNNIT} is currently in development mode.")

        if not settings.DEV_LOCKED_CHANNEL_ID:
            self.logger.info(f"Command executed: {ctx.command} by {ctx.author}")
            return

        if ctx.channel.id == settings.DEV_LOCKED_CHANNEL_ID:
            self.logger.info(f"Command executed: {ctx.command} by {ctx.author}")
            return

        dev_channel = self.get_channel(settings.DEV_LOCKED_CHANNEL_ID)
        if not isinstance(dev_channel, discord.TextChannel | discord.Thread):
            await ctx.send("Developer channel not found. Ensure it is set correctly.")
            self.logger.error(f"Developer channel {settings.DEV_LOCKED_CHANNEL_ID} not found")
            return

        await ctx.send(f"Please use {dev_channel.mention} instead which this session is locked to.")
        self.logger.info(f"Command from {ctx.author} in disallowed channel {ctx.channel}")

    async def _dispatch_slash_command_error(self, interaction, error):
        self.dispatch("slash_command_error", interaction, error)

    async def on_app_command_completion(self, interaction, command) -> None:
        usages = self.stats.command_usages[command.name]
        if interaction.user.guild_permissions.administrator:
            usages.admin_uses += 1
        if interaction.guild.id == settings.DEBUG_GUILD_ID:
            usages.dev_uses += 1
        usages.uses += 1

    @tasks.loop(minutes=settings.STAT_DUMP_FREQUENCY)
    async def output_stats(self):
        """
        Dumps the collected statistics for this runtime to a statistics file
        """
        try:
            # Update last write time
            self.stats.last_dump = datetime.now().isoformat()

            # Marshal data to dict
            data = asdict(self.stats)

            # Write to file
            with Path.open(self.stat_file, "w") as file:
                json.dump(data, file, indent=4)
                file.close()
        except Exception as e:
            self.logger.error(f"Error writing statistics to file: {e}")
            return

        self.logger.info("Statistics dumped to file")

    def run_bot(self) -> None:
        """Run the bot instance."""
        super().run(settings.BOT_TOKEN, reconnect=True)

# stl imports
import os
import logging


# third-party imports
import discord
from discord.ext import commands

# local imports
from backend.db.database import Database as db
from config import COG_PATH, ENABLE_CHATBOT
import backend.db as db


# Create the bot class, inheriting from commands.AutoShardedBot
class Bot(commands.AutoShardedBot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger("discord.main")
        self.logger.setLevel(logging.INFO)

    # Event that runs when the bot joins a new server
    async def on_guild_join(self, guild: discord.Guild):
        # check if guild exists, else create
        # TODO: refactor Database out of class so methods can be called directly
        guild_data = db.Database.get_document(db.Guild, guild.id)
        if not guild_data:
            guild_data = db.Guild(_id=guild.id)
            guild_data.save()
            self.logger.info(
                f"Created new guild entry for {guild.name} (ID: {guild.id})"
            )
        else:
            db.Database.sync_document_with_template(guild_data, db.Guild)
            self.logger.info(
                f"Guild {guild.name} (ID: {guild.id}) already exists and synced"
            )

    # Event that runs when a member joins a guild
    async def on_member_join(self, member: discord.Member):
        # check if guild exists, else create
        guild_data = db.Database.get_document(db.Guild, member.guild.id)
        if not guild_data:
            guild_data = db.Guild(_id=member.guild.id)
            guild_data.save()
            self.logger.info(
                f"Created new guild entry for {member.guild.name} (ID: {member.guild.id})"
            )
        else:
            db.sync_document_with_template(guild_data, db.Guild)

        # add member id to server users list
        guild_data.users.append(member.id)
        guild_data.save()
        self.logger.info(
            f"User {member.id} joined guild {member.guild.name} (ID: {member.guild.id})"
        ) 

    async def setup_hook(self):
        for filename in os.listdir(COG_PATH):
            if "ollama" in filename and ENABLE_CHATBOT == False:
                continue
            if filename.endswith(".py"):
                try:
                    await self.load_extension(
                        f"{COG_PATH.replace('/', '.')}.{filename[:-3]}"
                    )
                    self.logger.info(f"Loaded {filename}")
                except Exception as e:
                    self.logger.error(f"Failed to load {filename}: {e}")
            else:
                self.logger.warning(f"Skipping {filename}: Not a Python file")

    async def on_ready(self):
        # Notify when the bot is ready and print shard info
        self.logger.info(f"Logged in as {self.user.name} - {self.user.id}")
        self.logger.info(
            f"Connected to {len(self.guilds)} guilds across {self.shard_count} shards."
        )

    async def on_message(self, message):
        if self.allowed_channel_id is None:
            await self.process_commands(message)
        elif message.channel.id == self.allowed_channel_id:
            await self.process_commands(message)

    async def on_command(self, ctx):
        self.logger.info(f"Command executed: {ctx.command} by {ctx.author}")

    async def on_command_error(self, ctx, error):
        self.logger.error(f"{ctx.command}: {error}")
        await ctx.send(f"Failed to execute command: {error}")

# stl imports
import logging
import os

# third-party imports
import discord
from discord.ext import commands

# local imports
from backend.db.database import Database as db
from backend.db.documents.guild import Guild

from config import COG_PATH


# Create the bot class, inheriting from commands.AutoShardedBot
class Bot(commands.AutoShardedBot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger("discord.main")
        self.logger.setLevel(logging.INFO)

    # Event that runs when the bot joins a new server
    async def on_guild_join(self, guild: discord.Guild):
        # If already in guild, do nothing
        if db.get_document(Guild, guild.id):
            self.logger.info(
                f"Joined Guild: {guild.name} (ID: {guild.id}) already exists in database"
            )
            return

        # Else, add guild to data base
        new_guild = Guild(_id=guild.id)
        db.add_document(new_guild)
        self.logger.info(
            f"Inserted New Guild: {guild.name} (ID: {guild.id}) into database"
        )

    # Event that runs when a member joins a guild
    async def on_member_join(self, member: discord.Member):
        # get current guild data
        guild_doc = db.get_document(Guild, member.guild.id)

        # if guild does not exist, create it
        if not guild_doc:
            self.logger.warning(
                f"Guild {member.guild.name} does not exist in database for user {member.id} on join"
            )
            guild_doc = Guild(_id=member.guild.id)
            db.add_document(guild_doc)

        # add member id to server users list
        guild_doc.users.append(member.id)
        db.update_document(guild_doc, {"users": guild_doc.users})
        self.logger.info(
            f"User {member.id} joined guild {member.guild.name} (ID: {member.guild.id})"
        )

    async def setup_hook(self):
        for filename in os.listdir(COG_PATH):
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
        await ctx.send(error)

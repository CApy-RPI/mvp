import discord
from discord import app_commands
from discord.ext import commands

from capy_app.config import settings


class EventCogNew(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.guilds(
        discord.Object(id=settings.DEBUG_GUILD_ID if settings.DEBUG_GUILD_ID is not None else 0),
    )

    def event(self, interaction: discord.Interaction, action: str) -> None:
        # match action:
        #     case "create":
        #
        #     case "delete":
        #
        #     case "edit":
        #
        #     case "list":
        #     case "show":
        #     case "myevents"
        #
        #     case "announce":
        return

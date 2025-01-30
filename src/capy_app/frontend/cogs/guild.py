# stl imports
import logging

# third-party imports
import discord
from discord.ext import commands

# local imports
from backend.db.database import Database as db
from backend.db.documents.guild import Guild, GuildChannels, GuildRoles


class Guild(commands.Cog):
    """
    A class that represents a Discord Cog for managing server settings.
    """

    def __init__(self, bot: commands.Bot) -> None:
        """
        Initialize the Guild cog.

        Args:
            bot (commands.Bot): The bot instance.
        """
        self.bot = bot
        self.logger = logging.getLogger(
            f"discord.cog.{self.__class__.__name__.lower()}"
        )

    @commands.group(name="settings", help="Manage server settings")
    async def settings(self, ctx: commands.Context) -> None:
        """
        Group command for managing server settings.

        Args:
            ctx (commands.Context): The context of the command.
        """
        if ctx.invoked_subcommand is None:
            await ctx.send("Invalid settings command. Use !settings [list, set]")

    @settings.command(name="list", help="List server settings")
    async def list_settings(self, ctx: commands.Context) -> None:
        """
        List the current server settings.

        Args:
            ctx (commands.Context): The context of the command.
        """
        self.logger.info("Accessing guild from databse")
        guild = db.get_document(Guild, ctx.guild.id)
        self.logger.info("Guild data retrieved successfully")
        if not guild:
            await ctx.send("No settings configured for this server.")
            return

        embed = discord.Embed(
            title="Server Settings",
            color=discord.Color.green(),
        )

        embed.add_field(
            name="announcements_channel",
            value=guild.channels.announcements,
            inline=False,
        )
        embed.add_field(
            name="moderator_channel",
            value=guild.channels.moderator,
            inline=False,
        )
        embed.add_field(name="eboard_role", value=guild.roles.eboard, inline=False)

        await ctx.send(embed=embed)

    @settings.command(name="set", help="Change a server setting")
    @commands.has_permissions(administrator=True)
    async def modify_setting(
        self, ctx: commands.Context, name: str, value: str
    ) -> None:
        """
        Modify a server setting.

        Args:
            ctx (commands.Context): The context of the command.
            name (str): The name of the setting to change.
            value (str): The new value for the setting.
        """
        guild = db.get_document(Guild, ctx.guild.id)
        if not guild:
            guild = Guild(_id=ctx.guild.id)
            db.add_document(guild)

        # Remove any mention formatting from the value
        value = value.strip("<#@&>")

        try:
            # Map command names to document fields
            field_mapping = {
                "announcements_channel": "channels__announcements",
                "moderator_channel": "channels__moderator",
                "reports_channel": "channels__reports",
                "eboard_role": "roles__eboard",
                "admin_role": "roles__admin",
            }

            if name not in field_mapping:
                raise KeyError(f"Invalid setting: {name}")

            # Get the previous value using the field mapping
            field_parts = field_mapping[name].split("__")
            previous_value = getattr(getattr(guild, field_parts[0]), field_parts[1])

            # Update the value
            db.update_document(Guild, {field_mapping[name]: value})

            valid_embed = discord.Embed(
                title="Success!",
                description=f"'{name}' changed to '{value}' from '{previous_value}'.",
                color=discord.Color.green(),
            )
            await ctx.send(embed=valid_embed)
        except KeyError as e:
            fail_embed = discord.Embed(
                title="Invalid Setting",
                description=str(e),
                color=discord.Color.red(),
            )
            await ctx.send(embed=fail_embed)


# Setup function to load the cog
async def setup(bot: commands.Bot) -> None:
    """
    Setup function to load the Guild cog.

    Args:
        bot (commands.Bot): The bot instance.
    """
    await bot.add_cog(Guild(bot))

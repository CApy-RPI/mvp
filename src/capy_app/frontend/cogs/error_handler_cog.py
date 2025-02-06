"""Error handling cog for managing error messages and their status."""

import discord
from discord.ext import commands
from discord.ext.commands import Context
import typing
import logging

from config import settings


class ErrorHandlerCog(commands.Cog):
    """Cog for handling error messages and their resolution status."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = logging.getLogger(
            f"discord.cog.{self.__class__.__name__.lower()}"
        )

        # Emoji IDs for reactions
        self.RESOLVED_EMOJI = "✅"
        self.IGNORED_EMOJI = "❌"

    async def get_error_channel(self) -> typing.Optional[discord.TextChannel]:
        guild = self.bot.get_guild(settings.FAILED_COMMANDS_GUILD_ID)
        if not guild:
            self.logger.error(
                f"Could not find guild with ID {settings.FAILED_COMMANDS_GUILD_ID}"
            )
            return None

        error_channel = guild.get_channel(settings.FAILED_COMMANDS_CHANNEL_ID)
        if not isinstance(error_channel, discord.TextChannel):
            self.logger.error(
                f"Channel {settings.FAILED_COMMANDS_CHANNEL_ID} is not a text channel"
            )
            return None

        return error_channel

    async def log_error(self, ctx: Context[typing.Any], error: Exception) -> None:
        """Log error to designated channel with reaction controls.

        Args:
            ctx: Command context
            error: The error that occurred
        """
        error_channel = await self.get_error_channel()

        # Get channel name safely with ID
        channel_name = (
            f"{ctx.channel.name} ({ctx.channel.id})"
            if hasattr(ctx.channel, "name")
            else f"Unknown Channel ({ctx.channel.id})"
        )

        # Create invite if possible
        invite_link = "DM Channel"
        if ctx.guild and isinstance(ctx.channel, discord.TextChannel):
            try:
                invite = await ctx.channel.create_invite(
                    max_age=settings.FAILED_COMMANDS_INVITE_EXPIRY,
                    max_uses=settings.FAILED_COMMANDS_INVITE_USES,
                )
                invite_link = invite.url
            except discord.Forbidden:
                invite_link = "No permission to create invite"

        message_link = f"https://discord.com/channels/{ctx.guild.id if ctx.guild else '@me'}/{ctx.channel.id}/{ctx.message.id}"

        embed = discord.Embed(
            title="Command Error",
            description=f"Command: {ctx.command}\nError: {str(error)}",
            color=discord.Color.red(),
        )
        embed.add_field(
            name="Context",
            value=(
                f"Server: {ctx.guild.name} ({ctx.guild.id if ctx.guild else 'DM'})\n"
                f"Channel: {channel_name}\n"
                f"User: {ctx.author} ({ctx.author.id})\n"
                f"DM: {isinstance(ctx.channel, discord.DMChannel)}\n"
                f"[Jump to Message]({message_link})\n"
                f"Server Invite: {invite_link}"
            ),
        )
        embed.set_footer(text="React with ✅ when resolved or ❌ to ignore")

        try:
            error_message = await error_channel.send(embed=embed)
            await error_message.add_reaction(self.RESOLVED_EMOJI)
            await error_message.add_reaction(self.IGNORED_EMOJI)
            self.logger.info(
                f"Error logged to channel {error_channel.name} ({error_channel.id})"
            )
        except discord.Forbidden:
            self.logger.error(
                f"Missing permissions to send to error channel {error_channel.id}"
            )
        except Exception as e:
            self.logger.error(f"Failed to send error message: {e}")

    @commands.Cog.listener()
    async def on_reaction_add(
        self, reaction: discord.Reaction, user: discord.User
    ) -> None:
        """Handle reactions on error messages.

        Args:
            reaction: The reaction that was added
            user: The user who added the reaction
        """
        if user.bot:
            return

        message = reaction.message
        if not isinstance(message.channel, discord.TextChannel):
            return

        if message.channel.id != settings.FAILED_COMMANDS_CHANNEL_ID:
            return

        if str(reaction.emoji) not in [self.RESOLVED_EMOJI, self.IGNORED_EMOJI]:
            return

        # Update embed color based on reaction
        embed = message.embeds[0]
        if str(reaction.emoji) == self.RESOLVED_EMOJI:
            embed.color = discord.Color.green()
            status = "Resolved"
        else:
            embed.color = discord.Color.light_grey()
            status = "Ignored"

        embed.title = f"Command Error - {status}"
        await message.edit(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ErrorHandlerCog(bot))

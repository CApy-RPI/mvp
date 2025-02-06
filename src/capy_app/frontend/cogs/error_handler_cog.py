"""Error handling cog for managing error messages and their resolution status."""

import re
import time
import typing
import logging
import discord
from discord.ext import commands
from discord.ext.commands import Context

from config import settings


class ErrorHandlerCog(commands.Cog):
    """Cog for handling error messages and their resolution status."""

    def __init__(self, bot: commands.Bot) -> None:
        """Initialize the error handler cog."""
        self.bot = bot
        self.logger = logging.getLogger(
            f"discord.cog.{self.__class__.__name__.lower()}"
        )
        self.RESOLVED_EMOJI = "✅"
        self.IGNORED_EMOJI = "❌"
        self.INVITE_EMOJI = "❓"
        self.status_map: dict[str, tuple[discord.Color, str]] = {
            self.RESOLVED_EMOJI: (discord.Color.green(), "Resolved"),
            self.IGNORED_EMOJI: (discord.Color.light_grey(), "Ignored"),
        }

    async def _get_error_channel(self) -> typing.Optional[discord.TextChannel]:
        """Get the error logging channel."""
        guild = self.bot.get_guild(settings.FAILED_COMMANDS_GUILD_ID)
        if not guild:
            self.logger.error(
                f"Could not find guild with ID {settings.FAILED_COMMANDS_GUILD_ID}"
            )
            return None

        channel = guild.get_channel(settings.FAILED_COMMANDS_CHANNEL_ID)
        if not isinstance(channel, discord.TextChannel):
            self.logger.error(
                f"Channel {settings.FAILED_COMMANDS_CHANNEL_ID} is not a text channel"
            )
            return None

        return channel

    def _create_urls(self, ctx: Context[typing.Any]) -> dict[str, str]:
        """Create URLs for server, channel, and user."""
        if isinstance(ctx.channel, discord.DMChannel):
            return {
                "user": f"https://discord.com/users/{ctx.author.id}",
                "message": f"https://discord.com/channels/@me/{ctx.channel.id}/{ctx.message.id}",
            }

        if ctx.guild is None:
            raise ValueError("Guild context is None")

        return {
            "server": f"https://discord.com/guilds/{ctx.guild.id}",
            "channel": f"https://discord.com/channels/{ctx.guild.id}/{ctx.channel.id}",
            "user": f"https://discord.com/users/{ctx.author.id}",
            "message": f"https://discord.com/channels/{ctx.guild.id}/{ctx.channel.id}/{ctx.message.id}",
        }

    def _get_guild_info(
        self, guild: typing.Optional[discord.Guild], url: typing.Optional[str] = None
    ) -> str:
        """Get formatted guild information string."""
        if not guild:
            return "Direct Message"

        guild_text = f"{guild.name} ({guild.id})"
        return f"[{guild_text}]({url})" if url else guild_text

    def _get_channel_info(
        self,
        channel: typing.Union[
            discord.TextChannel,
            discord.VoiceChannel,
            discord.StageChannel,
            discord.Thread,
            discord.PartialMessageable,
            discord.GroupChannel,
        ],
        url: typing.Optional[str] = None,
    ) -> str:
        """Get formatted channel information string."""
        if isinstance(channel, discord.PartialMessageable):
            return f"Channel ID: {channel.id}"

        try:
            channel_text = f"#{channel.name} ({channel.id})"
            return f"[{channel_text}]({url})" if url else channel_text
        except AttributeError:
            return f"Unknown Channel ({channel.id})"

    def _create_error_embed(
        self,
        ctx: Context[typing.Any],
        error: Exception,
        urls: dict[str, str],
    ) -> discord.Embed:
        """Create error embed message."""
        embed = discord.Embed(
            title="Command Error",
            description=f"Command: {ctx.command}\nError: {str(error)}",
            color=discord.Color.red(),
        )

        # Add command message field
        embed.add_field(name="Message", value=f"`{ctx.message.content}`", inline=False)

        # Build context field based on channel type
        context_lines = []

        if not (is_dm := isinstance(ctx.channel, discord.DMChannel)):
            if not ctx.guild:
                raise ValueError("Guild context is None")
            if not ctx.channel:
                raise ValueError("Channel context is None")

            guild_info = self._get_guild_info(ctx.guild, urls.get("server"))
            channel_info = self._get_channel_info(ctx.channel, urls.get("channel"))

            context_lines.extend(
                [
                    f"Server: {guild_info}",
                    f"Channel: {channel_info}",
                ]
            )

        context_lines.extend(
            [
                f"User: [{ctx.author} ({ctx.author.id})]({urls['user']})",
                f"DM: {is_dm}",
                f"[Jump to Message]({urls['message']})",
            ]
        )

        embed.add_field(
            name="Context",
            value="\n".join(context_lines),
        )

        embed.set_footer(
            text="Status: Unresolved | React: ✅ Resolve, ❌ Ignore, ❓ Create Invite"
        )
        return embed

    async def _send_error_message(
        self, error_channel: discord.TextChannel, embed: discord.Embed
    ) -> None:
        """Send error message with reactions."""
        try:
            role_mention = f"<@&{settings.FAILED_COMMANDS_ROLE_ID}>"
            error_message = await error_channel.send(content=role_mention, embed=embed)
            for emoji in [self.RESOLVED_EMOJI, self.IGNORED_EMOJI, self.INVITE_EMOJI]:
                await error_message.add_reaction(emoji)
        except discord.Forbidden:
            self.logger.error(
                f"Missing permissions to send to error channel {error_channel.id}"
            )
        except Exception as e:
            self.logger.error(f"Failed to send error message: {e}")

    def _extract_ids_from_context(
        self, context_value: typing.Optional[str] = None
    ) -> typing.Tuple[typing.Optional[int], typing.Optional[int]]:
        """Extract guild and channel IDs from context field value.

        Args:
            context_value: The content of the context field

        Returns:
            Tuple of (guild_id, channel_id)
        """
        if context_value is None:
            return None, None

        guild_id = None
        channel_id = None

        for line in context_value.split("\n"):
            if "Server:" in line:
                try:
                    match = re.search(r"\((\d+)\)", line)
                    if match:
                        guild_id = int(match.group(1))
                except (ValueError, IndexError):
                    continue
            elif "Channel:" in line:
                try:
                    match = re.search(r"\((\d+)\)", line)
                    if match:
                        channel_id = int(match.group(1))
                except (ValueError, IndexError):
                    continue

        return guild_id, channel_id

    def _find_status_field_index(self, embed: discord.Embed) -> typing.Optional[int]:
        """Find the index of the Invite Status field if it exists."""
        for i, field in enumerate(embed.fields):
            if field.name == "Invite Status":
                return i
        return None

    def _add_status_field(
        self, embed: discord.Embed, message: str, success: bool = False
    ) -> None:
        """Update or add status field to embed with consistent formatting.

        Args:
            embed: Discord embed to modify
            message: Status message to display
            success: Whether this is a success message (default: False)
        """
        emoji = "✅" if success else "❌"
        status_value = f"{emoji} {message}"

        # Find existing status field
        field_index = self._find_status_field_index(embed)
        if field_index is not None:
            # Update existing field
            embed.set_field_at(
                field_index, name="Invite Status", value=status_value, inline=False
            )
        else:
            # Add new field if none exists
            embed.add_field(name="Invite Status", value=status_value, inline=False)

    async def _handle_invite_reaction(
        self, message: discord.Message, embed: discord.Embed
    ) -> None:
        """Handle invite reaction on error message."""
        context_field = next((f for f in embed.fields if f.name == "Context"), None)
        if not context_field:
            self.logger.error("Context field not found")
            return

        if not context_field.value:
            self.logger.error("Context field value is None")
            return

        # Check if this is a DM
        if "DM: True" in context_field.value:
            self._add_status_field(embed, "Cannot create invite to DM channel.")
            await message.edit(embed=embed)
            return

        guild_id, channel_id = self._extract_ids_from_context(context_field.value)
        if not guild_id or not channel_id:
            err_msg = "Could not extract server or channel information."
            self._add_status_field(embed, err_msg)
            self.logger.error(err_msg)
            await message.edit(embed=embed)
            return

        guild = self.bot.get_guild(guild_id)
        if not guild:
            self._add_status_field(embed, "Could not find the server.")
            self.logger.error(f"Could not find guild with ID {guild_id}")
            await message.edit(embed=embed)
            return

        channel = guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            self._add_status_field(embed, "Could not find the channel.")
            self.logger.error(f"Could not find channel with ID {channel_id}")
            await message.edit(embed=embed)
            return

        try:
            invite = await channel.create_invite(
                reason="Error Handler",
                max_age=settings.FAILED_COMMANDS_INVITE_EXPIRY,
                max_uses=settings.FAILED_COMMANDS_INVITE_USES,
            )
            expiry_time = int(time.time() + settings.FAILED_COMMANDS_INVITE_EXPIRY)
            self._add_status_field(
                embed,
                f"[Click to join]({invite.url})\nExpires <t:{expiry_time}:R>",
                success=True,
            )
        except discord.Forbidden:
            self._add_status_field(embed, "Missing permissions to create invite.")
            self.logger.error(
                f"Missing permissions to create invite in channel {channel_id}"
            )
        except Exception as e:
            self._add_status_field(embed, f"Failed to create invite: {str(e)}")
            self.logger.error(f"Failed to create invite: {e}")

        await message.edit(embed=embed)

    async def _log_error(self, ctx: Context[typing.Any], error: Exception) -> None:
        """Log error to designated channel with reaction controls."""
        error_channel = await self._get_error_channel()
        if not error_channel:
            self.logger.error("Error channel not found")
            return

        urls = self._create_urls(ctx)
        embed = self._create_error_embed(ctx, error, urls)
        await self._send_error_message(error_channel, embed)

    @commands.Cog.listener()
    async def on_reaction_add(
        self, reaction: discord.Reaction, user: discord.User
    ) -> None:
        """Handle reactions on error messages."""
        if user.bot:
            return

        message = reaction.message
        if not isinstance(message.channel, discord.TextChannel):
            return

        if message.channel.id != settings.FAILED_COMMANDS_CHANNEL_ID:
            return

        if not message.embeds or str(reaction.emoji) not in [
            self.RESOLVED_EMOJI,
            self.IGNORED_EMOJI,
            self.INVITE_EMOJI,
        ]:
            self.logger.error("Unknown reaction emoji")
            return

        embed = message.embeds[0]

        if str(reaction.emoji) == self.INVITE_EMOJI:
            await self._handle_invite_reaction(message, embed)
            return

        color, status = self.status_map[str(reaction.emoji)]
        embed.colour = color
        embed.title = f"Command Error - {status}"
        embed.set_footer(
            text=f"Status: {status} | React: ✅ Resolve, ❌ Ignore, ❓ New Invite"
        )
        await message.edit(embed=embed)

    @commands.Cog.listener()
    async def on_command_error(
        self, ctx: Context[typing.Any], error: Exception
    ) -> None:
        """Handle command execution errors.

        Args:
            ctx: Command context object
            error: Exception that occurred during command execution
        """
        await self._log_error(ctx, error)


async def setup(bot: commands.Bot) -> None:
    """Set up the error handler cog.

    Args:
        bot: The Discord bot instance
    """
    await bot.add_cog(ErrorHandlerCog(bot))

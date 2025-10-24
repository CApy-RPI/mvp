"""Error handling cog for managing error messages and their resolution status."""

# TODO: Replace colors with embed_colors.py

# Standard library imports
import datetime
import logging
import re
import time
import typing

# Third-party imports
import discord
from discord.ext import commands

# Local application imports
from config import settings


class ErrorHandlerCog(commands.Cog):
    async def _delete_messages(
        self, ctx: commands.Context[typing.Any], messages: list[discord.Message], status_str: str
    ) -> int:
        """Delete the provided messages and return the count of deleted messages."""
        deleted = 0
        for message in messages:
            await message.delete()
            deleted += 1
        await ctx.send(f"Successfully deleted {deleted} error messages with status: {status_str}")
        return deleted

    async def _count_matching_messages(
        self,
        error_channel: discord.TextChannel,
        status_str: str,
        status_map: dict[str, str],
        cutoff_time: datetime.datetime | None = None,
        seconds: int | None = None,
    ) -> tuple[int, list[discord.Message]]:
        """Count and collect matching messages in error channel."""
        if seconds is not None:
            cutoff_time = discord.utils.utcnow() - datetime.timedelta(seconds=float(seconds))
        count = 0
        matching_messages: list[discord.Message] = []
        async for message in error_channel.history(limit=None):
            if cutoff_time and message.created_at < cutoff_time:
                break
            if not message.embeds:
                continue
            current_status = self._get_message_status(message.embeds[0])
            if status_str == "all" or current_status == status_map.get(status_str):
                count += 1
                matching_messages.append(message)
        return count, matching_messages

    """Cog for handling error messages and their resolution status."""

    STATUS_MAP: dict[str, tuple[discord.Color, str]]

    def __init__(self, bot: commands.Bot) -> None:
        """Initialize the error handler cog."""
        self.bot = bot
        self.logger = logging.getLogger(f"discord.cog.{self.__class__.__name__.lower()}")

        self.RESOLVED_EMOJI = "✅"
        self.IGNORED_EMOJI = "❌"
        self.INVITE_EMOJI = "❓"
        self.STATUS_UNMARKED = "Unresolved"
        self.STATUS_RESOLVED = "Resolved"
        self.STATUS_IGNORED = "Ignored"
        self.STATUS_MAP: dict[str, tuple[discord.Color, str]] = {
            self.RESOLVED_EMOJI: (discord.Color.green(), self.STATUS_RESOLVED),
            self.IGNORED_EMOJI: (discord.Color.light_grey(), self.STATUS_IGNORED),
        }

    async def _get_error_channel(self) -> discord.TextChannel | None:
        """Get the error logging channel."""
        guild = self.bot.get_guild(settings.FAILED_COMMANDS_GUILD_ID)
        if not guild:
            self.logger.error(f"Could not find guild with ID {settings.FAILED_COMMANDS_GUILD_ID}")
            return None

        channel = guild.get_channel(settings.FAILED_COMMANDS_CHANNEL_ID)
        if not isinstance(channel, discord.TextChannel):
            self.logger.error(f"Channel {settings.FAILED_COMMANDS_CHANNEL_ID} is not a text channel")
            return None

        return channel

    def _create_urls(self, interaction: discord.Interaction[typing.Any]) -> dict[str, str]:
        """Create URLs for server, channel, and user."""
        if isinstance(interaction.channel, discord.DMChannel):
            return {
                "user": f"https://discord.com/users/{interaction.user.id}",
            }

        if interaction.guild is None:
            raise ValueError("Guild context is None")

        if interaction.channel is None:
            raise ValueError("Channel is None")

        return {
            "server": f"https://discord.com/guilds/{interaction.guild.id}",
            "channel": f"https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}",
            "user": f"https://discord.com/users/{interaction.user.id}",
        }

    def _get_guild_info(self, guild: discord.Guild | None, url: str | None = None) -> str:
        """Get formatted guild information string."""
        if not guild:
            return "Direct Message"

        guild_text = f"{guild.name} ({guild.id})"
        return f"[{guild_text}]({url})" if url else guild_text

    def _get_channel_info(
        self,
        channel: (
            discord.abc.GuildChannel
            | discord.GroupChannel
            | discord.DMChannel
            | discord.Thread
            | discord.PartialMessageable
        ),
        url: str | None = None,
    ) -> str:
        """Get formatted channel information string."""
        if isinstance(channel, discord.PartialMessageable):
            return f"Channel ID: {channel.id}"
        if isinstance(channel, discord.DMChannel):
            return f"DM Channel ({channel.id})"

        try:
            channel_text = f"#{channel.name} ({channel.id})"
            return f"[{channel_text}]({url})" if url else channel_text
        except AttributeError:
            return f"Unknown Channel ({channel.id})"

    # TODO: Since we have ephemerals, dropdowns, etc. now, I'm not sure how to best replicate the old ability to
    #   include & jump to the offending content.
    def _create_error_embed(
        self,
        interaction: discord.Interaction[typing.Any],
        error: Exception,
        urls: dict[str, str],
    ) -> discord.Embed:
        """Create error embed message."""
        if interaction.command is None:
            raise ValueError("Command is None")

        embed = discord.Embed(
            title=f"Command Error - {self.STATUS_UNMARKED}",
            description=f"Command: {interaction.command.name}\nError: {error!s}",
            color=discord.Color.red(),
        )

        # Build context field based on channel type
        context_lines = []

        if not (is_dm := isinstance(interaction.channel, discord.DMChannel)):
            if not interaction.guild:
                raise ValueError("Guild is None")
            if not interaction.channel:
                raise ValueError("Channel is None")

            guild_info = self._get_guild_info(interaction.guild, urls.get("server"))
            channel_info = self._get_channel_info(interaction.channel, urls.get("channel"))

            context_lines.extend(
                [
                    f"Server: {guild_info}",
                    f"Channel: {channel_info}",
                ]
            )

        context_lines.extend(
            [
                f"User: [{interaction.user} ({interaction.user.id})]({urls['user']})",
                f"DM: {is_dm}",
            ]
        )

        embed.add_field(
            name="Context",
            value="\n".join(context_lines),
        )

        embed.set_footer(text="Status: Unresolved | React: ✅ Resolve, ❌ Ignore, ❓ Create Invite")
        return embed

    async def _send_error_message(self, error_channel: discord.TextChannel, embed: discord.Embed) -> None:
        """Send error message with reactions."""
        try:
            role_mention = f"<@&{settings.FAILED_COMMANDS_ROLE_ID}>"
            error_message = await error_channel.send(content=role_mention, embed=embed)
            for emoji in [self.RESOLVED_EMOJI, self.IGNORED_EMOJI, self.INVITE_EMOJI]:
                await error_message.add_reaction(emoji)
        except discord.Forbidden:
            self.logger.error(f"Missing permissions to send to error channel {error_channel.id}")
        except Exception as e:
            self.logger.error(f"Failed to send error message: {e}")

    def _extract_ids_from_context(self, context_value: str | None = None) -> tuple[int | None, int | None]:
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

    def _find_status_field_index(self, embed: discord.Embed) -> int | None:
        """Find the index of the Invite Status field if it exists."""
        for i, field in enumerate(embed.fields):
            if field.name == "Invite Status":
                return i
        return None

    def _add_status_field(self, embed: discord.Embed, message: str, success: bool = False) -> None:
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
            embed.set_field_at(field_index, name="Invite Status", value=status_value, inline=False)
        else:
            # Add new field if none exists
            embed.add_field(name="Invite Status", value=status_value, inline=False)

    def _get_context_field(self, embed: discord.Embed) -> typing.Any | None:
        """Return the Context field from an embed, if present."""
        return next((f for f in embed.fields if f.name == "Context"), None)

    def _is_dm_from_context(self, context_value: str) -> bool:
        """Detect whether the context indicates a DM."""
        return "DM: True" in context_value

    async def _update_message_with_status(
        self,
        message: discord.Message,
        embed: discord.Embed,
        msg: str,
        *,
        success: bool = False,
    ) -> None:
        """Helper to add a status field and edit the message."""
        self._add_status_field(embed, msg, success=success)
        await message.edit(embed=embed)

    async def _create_invite_and_update(self, channel: discord.TextChannel) -> tuple[bool, str]:
        """Try to create a Discord invite and return (success, message)."""
        try:
            invite = await channel.create_invite(
                reason="Error Handler",
                max_age=settings.FAILED_COMMANDS_INVITE_EXPIRY,
                max_uses=settings.FAILED_COMMANDS_INVITE_USES,
            )
            expiry_time = int(time.time() + settings.FAILED_COMMANDS_INVITE_EXPIRY)
            return True, f"[Click to join]({invite.url})\nExpires <t:{expiry_time}:R>"
        except discord.Forbidden:
            self.logger.error(f"Missing permissions to create invite in channel {channel.id}")
            return False, "Missing permissions to create invite."
        except Exception as e:
            self.logger.error(f"Failed to create invite: {e}")
            return False, f"Failed to create invite: {e!s}"

    async def _handle_invite_reaction(self, message: discord.Message, embed: discord.Embed) -> None:
        """Handle invite reaction on error message."""
        context_field = self._get_context_field(embed)
        if not context_field or not context_field.value:
            self.logger.error("Context field not found or empty")
            return

        if self._is_dm_from_context(context_field.value):
            await self._update_message_with_status(message, embed, "Cannot create invite to DM channel.")
            return

        guild_id, channel_id = self._extract_ids_from_context(context_field.value)
        if not guild_id or not channel_id:
            self.logger.error("Could not extract server or channel information.")
            await self._update_message_with_status(message, embed, "Could not extract server or channel information.")
            return

        guild = self.bot.get_guild(guild_id)
        if not guild:
            self.logger.error(f"Could not find guild with ID {guild_id}")
            await self._update_message_with_status(message, embed, "Could not find the server.")
            return

        channel = guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            self.logger.error(f"Could not find channel with ID {channel_id}")
            await self._update_message_with_status(message, embed, "Could not find the channel.")
            return

        success, msg = await self._create_invite_and_update(channel)
        await self._update_message_with_status(message, embed, msg, success=success)

    async def _log_error(self, interaction: discord.Interaction[typing.Any], error: Exception) -> None:
        """Log error to designated channel with reaction controls."""
        error_channel = await self._get_error_channel()
        if not error_channel:
            self.logger.error("Error channel not found")
            return

        urls = self._create_urls(interaction)
        embed = self._create_error_embed(interaction, error, urls)
        await self._send_error_message(error_channel, embed)

    def _get_message_status(self, embed: discord.Embed) -> str:
        """Get the status of an error message from its embed."""
        if not embed.title:
            return self.STATUS_UNMARKED

        if self.STATUS_RESOLVED in embed.title:
            return self.STATUS_RESOLVED
        elif self.STATUS_IGNORED in embed.title:
            return self.STATUS_IGNORED
        return self.STATUS_UNMARKED

    async def _confirm_deletion(self, ctx: commands.Context[typing.Any], count: int, status: str) -> bool:
        """Ask for confirmation before deleting messages."""
        confirm_message = await ctx.send(
            f"Are you sure you want to delete {count} error messages with status '{status}'?\n"
            "React with ✅ to confirm or ❌ to cancel."
        )
        await confirm_message.add_reaction("✅")
        await confirm_message.add_reaction("❌")

        def check(reaction: discord.Reaction, user: discord.User) -> bool:
            return (
                user == ctx.author and str(reaction.emoji) in ["✅", "❌"] and reaction.message.id == confirm_message.id
            )

        try:
            reaction, _ = await self.bot.wait_for("reaction_add", timeout=30.0, check=check)
            await confirm_message.delete()
            return str(reaction.emoji) == "✅"
        except TimeoutError:
            await confirm_message.delete()
            await ctx.send("Deletion cancelled - timeout reached.")
            return False

    async def _create_interactive_menu(self, ctx: commands.Context[typing.Any]) -> tuple[str, str, str]:
        """Create an interactive menu for selecting ehc options."""
        operations: dict[str, str] = {"📋": "list", "🗑️": "clear"}
        statuses: dict[str, str] = {
            "✅": "resolved",
            "❌": "ignored",
            "⚠️": "unmarked",
            "📎": "all",
        }
        time_ranges: dict[str, str] = {
            "1️⃣": "1h",
            "2️⃣": "1d",
            "3️⃣": "7d",
            "4️⃣": "30d",
            "5️⃣": "all",
        }

        async def get_selection(message: discord.Message, options: dict[str, str], prompt: str) -> str:
            self.logger.info(f"Prompting user with: {prompt}")
            for emoji in options:
                await message.add_reaction(emoji)

            def check(reaction: discord.Reaction, user: discord.User) -> bool:
                return user == ctx.author and str(reaction.emoji) in options

            try:
                reaction, _ = await self.bot.wait_for("reaction_add", timeout=30.0, check=check)
                return options[str(reaction.emoji)]
            except TimeoutError:
                raise commands.CommandError("Selection timed out") from None

        # Operation selection
        op_msg = await ctx.send("Select operation:\n📋 List\n🗑️ Clear")
        operation = await get_selection(op_msg, operations, "operation")
        await op_msg.delete()

        # Status selection
        status_msg = await ctx.send("Select status:\n✅ Resolved\n❌ Ignored\n⚠️ Unmarked\n📎 All")
        status = await get_selection(status_msg, statuses, "status")
        await status_msg.delete()

        # Time range selection
        time_msg = await ctx.send("Select time range:\n1️⃣ 1 hour\n2️⃣ 1 day\n3️⃣ 7 days\n4️⃣ 30 days\n5️⃣ All time")
        time_range = await get_selection(time_msg, time_ranges, "time range")
        await time_msg.delete()

        return operation, status, time_range

    async def _error_handler_helper(
        self,
        ctx: commands.Context[typing.Any],
    ) -> bool:
        if not ctx.guild or ctx.guild.id != settings.FAILED_COMMANDS_GUILD_ID:
            await ctx.send("This command can only be used in the designated error handling server.")
            return True

        if ctx.channel.id != settings.FAILED_COMMANDS_CHANNEL_ID:
            await ctx.send("This command can only be used in the designated error handling channel.")
            return True

        return False

    async def _stringcheck(
        self,
        ctx,
        operation: str,
        status: str,
        time_range: str,
        time_ranges: dict[str, int | None],
    ) -> bool:
        """Check if the provided operation, status, and time range are valid."""
        if operation not in ["list", "clear"]:
            await ctx.send("Invalid operation. Use: list or clear")
            return True

        if status not in ["resolved", "ignored", "unmarked", "all"]:
            await ctx.send("Invalid status. Use: resolved, ignored, unmarked, or all")
            return True

        if time_range not in time_ranges:
            await ctx.send("Invalid time range. Use: 1h, 1d, 7d, 30d, or all")
            return True

        return False

    @commands.command(name="ehc", hidden=True)
    @commands.has_permissions(manage_messages=True)
    async def error_handler_command(
        self,
        ctx: commands.Context[typing.Any],
        operation: str | None = None,
        status: str | None = None,
        time_range: str | None = None,
    ) -> None:
        """Manage error messages.

        Args:
            ctx: The command context
            operation: Operation to perform (list/clear)
            status: Status of messages to handle (resolved/ignored/unmarked/all)
            time_range: Time range to look back (1h/1d/7d/30d/all)
        """
        # Check if command is used in the correct guild and channel
        if self._error_handler_helper(ctx):
            return

        # Collect parameters, falling back to interactive menu
        try:
            if any(param is None for param in [operation, status, time_range]):
                operation, status, time_range = await self._create_interactive_menu(ctx)
        except commands.CommandError as e:
            await ctx.send(f"Error: {e!s}")
            return

        # Normalize
        operation_str = str(operation).lower()
        status_str = str(status).lower()
        time_range_str = str(time_range).lower()

        # Validate
        time_ranges: dict[str, int | None] = {
            "1h": 3600,
            "1d": 86400,
            "7d": 604800,
            "30d": 2592000,
            "all": None,
        }
        if await self._stringcheck(ctx, operation_str, status_str, time_range_str, time_ranges):
            return

        # Resolve channel
        error_channel = await self._get_error_channel()
        if not error_channel:
            await ctx.send("Error channel not found")
            return
        status_map: dict[str, str] = {
            "resolved": self.STATUS_RESOLVED,
            "ignored": self.STATUS_IGNORED,
            "unmarked": self.STATUS_UNMARKED,
        }

        # Calculate cutoff time if needed
        cutoff_time: datetime.datetime | None = None
        seconds = time_ranges[time_range_str]

        # Count matching messages
        count, matching_messages = await self._count_matching_messages(
            error_channel, status_str, status_map, cutoff_time, seconds
        )
        if count == 0:
            await ctx.send(f"No messages found with status: {status_str}")
            return

        if operation_str == "list":
            embed = discord.Embed(
                title="Error Message Summary",
                description=(
                    f"Found {count} messages matching criteria:\nStatus: {status_str}\nTime range: {time_range_str}"
                ),
                color=discord.Color.blue(),
            )
            await ctx.send(embed=embed)
        else:
            # Handle clear operation
            if not await self._confirm_deletion(ctx, count, status_str):
                await ctx.send("Deletion cancelled.")
                return
            await self._delete_messages(ctx, matching_messages, status_str)

    # TODO buttons might be a more elegant way to do this.
    @commands.Cog.listener()
    async def on_reaction_add(
        self,
        reaction: discord.Reaction,
        user: discord.User | discord.Member,
    ) -> None:
        """Handle reactions on error messages."""
        if user.bot:
            return

        message = reaction.message
        if not isinstance(message.channel, discord.TextChannel):
            return

        if message.channel.id != settings.FAILED_COMMANDS_CHANNEL_ID or not message.embeds:
            return

        embed = message.embeds[0]
        if not embed.title or "Command Error" not in embed.title:
            return

        if str(reaction.emoji) not in [
            self.RESOLVED_EMOJI,
            self.IGNORED_EMOJI,
            self.INVITE_EMOJI,
        ]:
            self.logger.error("Unknown reaction emoji")
            return

        if str(reaction.emoji) == self.INVITE_EMOJI:
            await self._handle_invite_reaction(message, embed)
            return

        color, status = self.STATUS_MAP[str(reaction.emoji)]
        embed.colour = color
        embed.title = f"Command Error - {status}"
        embed.set_footer(text=f"Status: {status} | React: ✅ Resolve, ❌ Ignore, ❓ New Invite")
        await message.edit(embed=embed)

    @commands.Cog.listener()
    async def on_slash_command_error(self, interaction: discord.Interaction, error: Exception) -> None:
        """Handle slash command execution errors.

        Args:
            interaction: Command interaction
            error: Exception that occurred during command execution
        """
        if interaction.command is None:
            raise ValueError("Command is None")

        if isinstance(interaction.command, discord.app_commands.Command):
            cmd_name = interaction.command.qualified_name
        else:
            cmd_name = interaction.command.name

        self.logger.error(f"{cmd_name}: {error}")

        err_msg = f"Failed to execute command: {error}"
        if interaction.response.is_done():
            await interaction.followup.send(err_msg)
        else:
            await interaction.response.send_message(err_msg, ephemeral=True)

        await self._log_error(interaction, error)


async def setup(bot: commands.Bot) -> None:
    """Set up the error handler cog.

    Args:
        bot: The Discord bot instance
    """
    await bot.add_cog(ErrorHandlerCog(bot))

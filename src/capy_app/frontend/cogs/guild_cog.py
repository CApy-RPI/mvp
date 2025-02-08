"""Guild settings management cog."""

import typing
import logging
import discord
from discord.ext import commands

from backend.db.database import Database as db
from frontend.utils import colors
from frontend.utils.prompt_helper import (
    prompt_menu,
    prompt_one,
    prompt_many,
    MenuTimeout,
)
from frontend.cogs.handler.guild_handler_cog import GuildHandlerCog


class GuildCog(commands.Cog):
    """Manages guild configuration settings."""

    def __init__(self, bot: commands.Bot) -> None:
        """Initialize guild management cog."""
        self.bot = bot
        self.logger = logging.getLogger(
            f"discord.cog.{self.__class__.__name__.lower()}"
        )
        self._init_settings_config()

    def _init_settings_config(self) -> None:
        """Initialize settings configuration maps."""
        self.settings_config: typing.Dict[str, typing.Dict[str, typing.Any]] = {
            "channels": {
                "emoji_map": {"📢": "announcements", "🛡️": "moderator", "📝": "reports"},
                "prompt": "Select channel:\n📢 Announcements\n🛡️ Moderator\n📝 Reports",
                "field_prefix": "channels",
            },
            "roles": {
                "emoji_map": {
                    "🎫": "visitor",
                    "👥": "member",
                    "📋": "eboard",
                    "🔑": "admin",
                },
                "prompt": "Select role:\n🎫 Visitor\n👥 Member\n📋 E-Board\n🔑 Admin",
                "field_prefix": "roles",
            },
        }

    async def _get_setting_value(
        self, ctx: commands.Context[typing.Any], setting_type: str
    ) -> typing.Optional[typing.Tuple[str, typing.Union[int, str]]]:
        """Get setting value through menu interaction."""
        config = self.settings_config.get(setting_type)
        if not config:
            return None

        setting_name = await prompt_menu(
            ctx,
            config["emoji_map"],
            config["prompt"],
            title="Settings",
            color=colors.GUILD,
        )
        if not setting_name:
            return None

        response = await prompt_one(
            ctx,
            f"Please mention the {setting_name} to set",
            title=f"Set {setting_name.title()}",
            color=colors.GUILD,
        )
        if not response:
            return None

        try:
            value: typing.Union[int, str] = (
                int(response.channel_mentions[0].id)
                if setting_type == "channels"
                else str(response.role_mentions[0].id)
            )
            await response.delete()
            return f"{config['field_prefix']}__{setting_name}", value
        except (IndexError, AttributeError):
            return None

    @commands.group(name="guild", aliases=["server"])
    @commands.has_permissions(administrator=True)
    async def guild(self, ctx: commands.Context[typing.Any]) -> None:
        """Manage guild settings."""
        if ctx.invoked_subcommand is not None:
            return

        action = await prompt_menu(
            ctx,
            {"👀": "show", "⚙️": "edit"},
            "👀 Show settings\n⚙️ Edit settings",
            title="Server Management",
            color=colors.GUILD,
        )

        if action == "show":
            await self.show_settings(ctx)
        elif action == "edit":
            await self.edit_settings(ctx)

    async def _update_setting(
        self,
        ctx: commands.Context[typing.Any],
        field_name: str,
        value: typing.Union[int, str],
        setting_type: str,
    ) -> None:
        """Update a setting and send confirmation."""
        guild = await GuildHandlerCog.ensure_guild_exists(ctx.guild.id)
        if not guild:
            embed = discord.Embed(
                title="Error",
                description="Could not access guild settings.",
                color=colors.ERROR,
            )
            await ctx.send(embed=embed)
            return

        db.update_document(guild, {field_name: value})

        setting_name = field_name.split("__")[1]
        mention = f"<#{value}>" if setting_type == "channels" else f"<@&{value}>"

        embed = discord.Embed(
            title=f"{setting_type.title()[:-1]} Updated",
            description=f"{setting_type.title()[:-1]} {mention} has been set as the {setting_name} {setting_type[:-1]}",
            color=colors.SUCCESS,
        )
        await ctx.send(embed=embed)

    async def _bulk_set_settings(
        self, ctx: commands.Context[typing.Any], setting_type: str
    ) -> None:
        """Configure all channels or roles at once."""
        config = self.settings_config.get(setting_type)
        if not config:
            return

        names = list(config["emoji_map"].values())
        prompts = [f"Please mention the {name} to set" for name in names]

        responses = await prompt_many(
            ctx, prompts, title=f"Set {setting_type.title()}", color=colors.GUILD
        )

        updates = {}
        for name, response in zip(names, responses):
            try:
                value = (
                    int(response.channel_mentions[0].id)
                    if setting_type == "channels"
                    else str(response.role_mentions[0].id)
                )
                updates[f"{config['field_prefix']}__{name}"] = value
                await response.delete()
            except (IndexError, AttributeError):
                continue

        if updates:
            guild = await GuildHandlerCog.ensure_guild_exists(ctx.guild.id)
            if guild:
                db.update_document(guild, updates)
                await self._send_update_summary(ctx, updates, setting_type)
            else:
                embed = discord.Embed(
                    title="Error",
                    description="Could not access guild settings.",
                    color=colors.ERROR,
                )
                await ctx.send(embed=embed)

    async def _send_update_summary(
        self,
        ctx: commands.Context[typing.Any],
        updates: typing.Dict[str, typing.Union[int, str]],
        setting_type: str,
    ) -> None:
        """Send a summary of updated settings."""
        embed = discord.Embed(
            title=f"{setting_type.title()} Configuration Updated",
            color=colors.SUCCESS,
        )

        for field, value in updates.items():
            setting_name = field.split("__")[1]
            mention = f"<#{value}>" if setting_type == "channels" else f"<@&{value}>"
            embed.add_field(name=setting_name.title(), value=mention, inline=True)

        await ctx.send(embed=embed)

    @guild.command(name="show")
    async def show_settings(self, ctx: commands.Context[typing.Any]) -> None:
        """Display current guild settings."""
        guild = await GuildHandlerCog.ensure_guild_exists(ctx.guild.id)
        if not guild:
            await ctx.send("No settings configured for this guild.")
            return

        embed = discord.Embed(title="Server Settings", color=colors.GUILD)

        # Add channel settings
        channels = [
            (name, getattr(guild.channels, name))
            for name in ["announcements", "moderator", "reports"]
        ]
        channel_text = "\n".join(
            f"{name.capitalize()}: <#{id}>" if id else f"{name.capitalize()}: Not set"
            for name, id in channels
        )
        embed.add_field(
            name="Channels",
            value=channel_text or "No channels configured",
            inline=False,
        )

        # Add role settings
        roles = [
            (name, getattr(guild.roles, name))
            for name in ["visitor", "member", "eboard", "admin"]
        ]
        role_text = "\n".join(
            f"{name.capitalize()}: <@&{id}>" if id else f"{name.capitalize()}: Not set"
            for name, id in roles
        )
        embed.add_field(
            name="Roles",
            value=role_text or "No roles configured",
            inline=False,
        )

        await ctx.send(embed=embed)

    @guild.group(name="edit")
    async def edit_settings(self, ctx: commands.Context[typing.Any]) -> None:
        """Interactive menu for editing guild settings."""
        if ctx.invoked_subcommand is not None:
            return

        options = {
            "📢": "channels",
            "👥": "roles",
            "📋": "allchannels",
            "📑": "allroles",
        }
        prompt = (
            "Select setting type to configure:\n"
            "📢 Single Channel\n"
            "👥 Single Role\n"
            "📋 All Channels\n"
            "📑 All Roles"
        )

        try:
            setting_type = await prompt_menu(
                ctx, options, prompt, title="Edit Settings", color=colors.GUILD
            )
            if setting_type in ["channels", "roles"]:
                result = await self._get_setting_value(ctx, setting_type)
                if result:
                    await self._update_setting(ctx, *result, setting_type)
            elif setting_type == "allchannels":
                await self.edit_all_channels(ctx)
            elif setting_type == "allroles":
                await self.edit_all_roles(ctx)
        except MenuTimeout:
            embed = discord.Embed(
                title="Timeout",
                description="Menu selection timed out.",
                color=colors.WARNING,
            )
            await ctx.send(embed=embed)

    @edit_settings.command(name="channel")
    async def edit_channel(self, ctx: commands.Context[typing.Any]) -> None:
        """Configure channel settings directly."""
        result = await self._get_setting_value(ctx, "channels")
        if result:
            await self._update_setting(ctx, *result, "channels")

    @edit_settings.command(name="role")
    async def edit_role(self, ctx: commands.Context[typing.Any]) -> None:
        """Configure role settings directly."""
        result = await self._get_setting_value(ctx, "roles")
        if result:
            await self._update_setting(ctx, *result, "roles")

    @edit_settings.command(name="allchannels")
    async def edit_all_channels(self, ctx: commands.Context[typing.Any]) -> None:
        """Configure all channels at once."""
        await self._bulk_set_settings(ctx, "channels")

    @edit_settings.command(name="allroles")
    async def edit_all_roles(self, ctx: commands.Context[typing.Any]) -> None:
        """Configure all roles at once."""
        await self._bulk_set_settings(ctx, "roles")


async def setup(bot: commands.Bot) -> None:
    """Set up the Guild cog.

    Args:
        bot: The Discord bot instance
    """
    await bot.add_cog(GuildCog(bot))

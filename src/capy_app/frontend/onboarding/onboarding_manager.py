"""Onboarding manager for controlling first-run behavior when the bot joins a guild.

This utility centralizes onboarding so behavior can be adjusted via settings
without touching core event handlers. It focuses on safe defaults and graceful
degradation when permissions are limited.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import discord

from config import settings

logger = logging.getLogger("discord.onboarding")


@dataclass(slots=True)
class OnboardingConfig:
    enabled: bool
    mode: str  # "announce" | "dm" | "silent"
    require_manage_guild: bool
    fallback_channel_id: int | None
    docs_url: str | None
    message: str

    @classmethod
    def from_settings(cls) -> OnboardingConfig:
        return cls(
            enabled=bool(settings.ONBOARDING_ENABLED),
            mode=(settings.ONBOARDING_MODE or "announce").lower(),
            require_manage_guild=bool(settings.ONBOARDING_REQUIRE_MANAGE_GUILD),
            fallback_channel_id=settings.ONBOARDING_FALLBACK_CHANNEL_ID,
            docs_url=settings.ONBOARDING_DOCS_URL,
            message=(settings.ONBOARDING_MESSAGE or "Thanks for adding me!"),
        )


class OnboardingManager:
    def __init__(self, config: OnboardingConfig | None = None) -> None:
        self.cfg = config or OnboardingConfig.from_settings()
        self.logger = logger

    async def handle_guild_join(self, guild: discord.Guild) -> None:
        """Entry point for guild join onboarding.

        Behavior is controlled via settings. Safe no-op when disabled or in
        "silent" mode.
        """
        if not isinstance(guild, discord.Guild):  # defensive
            return

        if not self.cfg.enabled or self.cfg.mode == "silent":
            self.logger.info("Onboarding disabled or silent; skipping message.")
            return

        if self.cfg.mode == "dm":
            await self._try_dm_guild_owner(guild)
            return

        # Default: announce mode
        channel = await self._find_postable_channel(guild)
        if not channel:
            self.logger.warning(
                "No suitable channel found for onboarding in guild %s (%s)",
                guild.name,
                guild.id,
            )
            return

        await self._post_intro(channel, guild)

    async def _find_postable_channel(self, guild: discord.Guild) -> discord.abc.MessageableChannel | None:
        # 1) Prefer system channel if sendable
        if guild.system_channel and self._can_send(guild.system_channel):
            return guild.system_channel

        # 2) If configured, try fallback channel id
        if self.cfg.fallback_channel_id:
            ch = guild.get_channel(self.cfg.fallback_channel_id)
            if isinstance(ch, discord.TextChannel) and self._can_send(ch):
                return ch

        # 3) First text channel we can send to
        for ch in guild.text_channels:
            if self._can_send(ch):
                return ch
        return None

    def _can_send(self, channel: discord.TextChannel) -> bool:
        perms = channel.permissions_for(channel.guild.me) if channel.guild.me else None
        return bool(perms and perms.send_messages and perms.embed_links)

    async def _post_intro(self, channel: discord.TextChannel, guild: discord.Guild) -> None:
        embed = discord.Embed(
            title=f"👋 Thanks for inviting me to {guild.name}!",
            description=self._build_intro_description(),
            color=discord.Color.blurple(),
        )

        view = None
        # Add a docs button if provided
        if self.cfg.docs_url:
            view = discord.ui.View()
            view.add_item(discord.ui.Button(label="Setup Guide", url=self.cfg.docs_url))

        try:
            await channel.send(embed=embed, view=view)
            self.logger.info("Posted onboarding intro to %s (%s)", guild.name, guild.id)
        except Exception as e:
            self.logger.error("Failed to post onboarding intro: %s", e)

    async def _try_dm_guild_owner(self, guild: discord.Guild) -> None:
        owner = guild.owner
        if not owner:
            self.logger.warning("No owner found to DM for guild %s (%s)", guild.name, guild.id)
            return
        try:
            dm = await owner.create_dm()
            await dm.send(self._build_owner_dm(guild))
            self.logger.info("Sent onboarding DM to owner in %s (%s)", guild.name, guild.id)
        except Exception as e:
            self.logger.error("Failed to DM guild owner: %s", e)

    def _build_intro_description(self) -> str:
        lines: list[str] = []
        lines.append(self.cfg.message)

        if self.cfg.require_manage_guild:
            lines.append("\nOnly members with 'Manage Server' should configure settings.")

        # Hint at next actions; avoid referencing commands that may not be synced
        if settings.WHO_DUNNIT:
            lines.append(f"Hosted by: {settings.WHO_DUNNIT}")

        if self.cfg.docs_url:
            lines.append("See the Setup Guide button below to start.")

        return "\n".join(lines)

    def _build_owner_dm(self, guild: discord.Guild) -> str:
        msg = [
            f"Hi! Thanks for adding me to {guild.name}.",
            self.cfg.message,
        ]
        if self.cfg.require_manage_guild:
            msg.append("Only members with 'Manage Server' should run setup.")
        if self.cfg.docs_url:
            msg.append(f"Setup Guide: {self.cfg.docs_url}")
        return "\n\n".join(msg)

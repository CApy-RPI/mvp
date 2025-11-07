"""Onboarding manager for controlling first-run behavior when the bot joins a guild.

This utility centralizes onboarding so behavior can be adjusted via settings
without touching core event handlers. It focuses on safe defaults and graceful
degradation when permissions are limited.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

import discord
from backend.db.database import Database
from backend.db.documents.user import User

from config import settings

from .profile_scanner import ProfileBatchHelper

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
        # Initialize profile scanning helper (used for batching/extensibility)
        try:
            self.profile_helper: object | None = ProfileBatchHelper()
        except Exception:
            self.profile_helper = None

    class CreateProfileView(discord.ui.View):
        """View with a button that launches the profile creation flow ephemerally."""

        def __init__(self) -> None:
            super().__init__(timeout=300)

        @discord.ui.button(label="Create Your Profile", style=discord.ButtonStyle.primary)
        async def create_profile(self, interaction: discord.Interaction, _button: discord.ui.Button[object]) -> None:  # type: ignore[name-defined]
            # Route to the ProfileCog flow so it can present the modal ephemerally
            try:
                logger.info(
                    "onboarding: create_profile clicked by user=%s guild=%s",
                    getattr(interaction.user, "id", None),
                    getattr(getattr(interaction, "guild", None), "id", None),
                )
                cog = interaction.client.get_cog("ProfileCog") if interaction.client else None  # type: ignore[attr-defined]
                if not cog:
                    await interaction.response.send_message(
                        "Profile system is unavailable right now. Please try again later.",
                        ephemeral=True,
                    )
                    return

                # The ProfileCog exposes handle_profile(interaction, action)
                await cog.handle_profile(interaction, "create")  # type: ignore[attr-defined]
            except Exception as e:
                logger.error("Failed to start profile creation from onboarding: %s", e)
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "Something went wrong starting your profile. Try /profile create.",
                        ephemeral=True,
                    )

    class SetupServerView(discord.ui.View):
        """View that offers a button to start the server setup flow."""

        def __init__(self, docs_url: str | None, require_manage: bool) -> None:
            super().__init__(timeout=600)
            self.require_manage = require_manage
            if docs_url:
                self.add_item(discord.ui.Button(label="Setup Guide", url=docs_url))

        @discord.ui.button(label="Start Server Setup", style=discord.ButtonStyle.primary)
        async def start_setup(self, interaction: discord.Interaction, _button: discord.ui.Button[object]) -> None:  # type: ignore[name-defined]
            try:
                logger.info(
                    "onboarding: start_setup clicked by user=%s guild=%s",
                    getattr(interaction.user, "id", None),
                    getattr(getattr(interaction, "guild", None), "id", None),
                )
                # Optional permission gate
                if self.require_manage and not getattr(interaction.user.guild_permissions, "manage_guild", False):
                    await interaction.response.send_message(
                        "Only members with 'Manage Server' can run setup.",
                        ephemeral=True,
                    )
                    return

                cog = interaction.client.get_cog("GuildCog") if interaction.client else None  # type: ignore[attr-defined]
                if not cog:
                    await interaction.response.send_message(
                        "Setup system is unavailable right now. Please try again later.",
                        ephemeral=True,
                    )
                    return

                await cog.setup_flow(interaction)  # type: ignore[attr-defined]
            except Exception as e:
                logger.error("Failed to start server setup from onboarding: %s", e)
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "Something went wrong starting setup. Try /server setup.",
                        ephemeral=True,
                    )

    async def handle_guild_join(self, guild: discord.Guild) -> None:
        """Entry point for guild join onboarding.

        Behavior is controlled via settings. Safe no-op when disabled or in
        "silent" mode.
        """
        if not isinstance(guild, discord.Guild):  # defensive
            return

        self.logger.info(
            "onboarding: handle_guild_join guild=%s mode=%s require_manage=%s",
            getattr(guild, "id", None),
            self.cfg.mode,
            self.cfg.require_manage_guild,
        )

        if not self.cfg.enabled or self.cfg.mode == "silent":
            self.logger.info("onboarding: disabled or silent; skipping intro")
            return

        if self.cfg.mode == "dm":
            await self._try_dm_guild_owner(guild)
            # Also DM members without profiles in DM-only mode
            # await self._dm_missing_profiles(guild)
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
        # After posting intro, do not DM members (temporarily disabled).
        # Instead, run a non-intrusive scan via the helper and log the results.
        try:
            if self.profile_helper:
                # type: ignore[union-attr]
                result = await self.profile_helper.scan_profiles(guild)  # type: ignore[attr-defined]
                self.logger.info(
                    "onboarding: scan complete with_profiles=%d without_profiles=%d",
                    len(result.with_profiles),
                    len(result.without_profiles),
                )
                self.logger.debug(
                    "onboarding: with_profiles=%s",
                    ",".join(str(x) for x in result.with_profiles),
                )
                self.logger.debug(
                    "onboarding: without_profiles=%s",
                    ",".join(str(x) for x in result.without_profiles),
                )
        except Exception as e:
            self.logger.error("onboarding: profile scan failed: %s", e)

    async def _find_postable_channel(self, guild: discord.Guild) -> discord.abc.MessageableChannel | None:
        # 1) Prefer system channel if sendable
        if guild.system_channel and self._can_send(guild.system_channel):
            self.logger.debug(
                "onboarding: using system channel %s for intro",
                getattr(guild.system_channel, "id", None),
            )
            return guild.system_channel

        # 2) If configured, try fallback channel id
        if self.cfg.fallback_channel_id:
            ch = guild.get_channel(self.cfg.fallback_channel_id)
            if isinstance(ch, discord.TextChannel) and self._can_send(ch):
                self.logger.debug(
                    "onboarding: using fallback channel %s for intro",
                    ch.id,
                )
                return ch

        # 3) First text channel we can send to
        for ch in guild.text_channels:
            if self._can_send(ch):
                self.logger.debug("onboarding: using first postable channel %s", ch.id)
                return ch
        self.logger.debug("onboarding: no postable channel found")
        return None

    def _can_send(self, channel: discord.TextChannel) -> bool:
        perms = channel.permissions_for(channel.guild.me) if channel.guild.me else None
        return bool(perms and perms.send_messages and perms.embed_links)

    async def _post_intro(self, channel: discord.TextChannel, guild: discord.Guild) -> None:
        # Compute a quick hint on how many members likely need profiles
        missing_profiles = 0
        try:
            for m in guild.members:
                if m.bot:
                    continue
                if not Database.get_document(User, m.id):
                    missing_profiles += 1
        except Exception as e:
            self.logger.debug("Unable to compute missing profiles: %s", e)
        else:
            self.logger.info(
                "onboarding: estimated members missing profiles=%s guild=%s",
                missing_profiles,
                getattr(guild, "id", None),
            )

        embed = discord.Embed(
            title=f"👋 Thanks for inviting me to {guild.name}!",
            description=self._build_intro_description(),
            color=discord.Color.blurple(),
        )

        # Add contextual info about profiles
        if missing_profiles:
            embed.add_field(
                name="Get Everyone Set Up",
                value=(
                    f"It looks like about {missing_profiles} member(s) may still need a profile.\n"
                    "Use /profile to create or update your profile."
                ),
                inline=False,
            )

        # Build the action view: Start Setup button (+ optional docs URL)
        view: discord.ui.View = self.SetupServerView(self.cfg.docs_url, self.cfg.require_manage_guild)

        try:
            await channel.send(embed=embed, view=view)
            self.logger.info("Posted onboarding intro to %s (%s)", guild.name, guild.id)
        except Exception as e:
            self.logger.error("Failed to post onboarding intro: %s", e)

    async def _dm_missing_profiles(self, guild: discord.Guild) -> None:
        """Direct-message each human member without a profile with a create button.

        Best-effort: skips users who block DMs or if errors occur. Adds small
        delays to be gentle on rate limits.
        """

        # TODO: handle at scale case thousands of members
        create_view = self.CreateProfileView()
        count = 0
        total_humans = sum(1 for m in guild.members if not m.bot)
        self.logger.info(
            "onboarding: DM pass starting humans=%s guild=%s",
            total_humans,
            getattr(guild, "id", None),
        )
        for member in guild.members:
            try:
                if member.bot:
                    continue
                if Database.get_document(User, member.id):
                    continue

                dm = await member.create_dm()
                embed = discord.Embed(
                    title="Let's set up your Capy profile",
                    description=(
                        "Profiles let you register your student info and majors, "
                        "and are required for event access. Click the button below "
                        "to create yours now."
                    ),
                    color=discord.Color.blurple(),
                )
                await dm.send(embed=embed, view=create_view)
                count += 1
                # Light pacing to reduce burstiness
                await asyncio.sleep(0.4)
            except Exception as e:
                self.logger.debug("Skipping DM to %s (%s): %s", member, member.id, e)
                continue
        if count:
            self.logger.info("onboarding: DM'd %d member(s) missing profiles in %s (%s)", count, guild.name, guild.id)
        else:
            self.logger.info("onboarding: no members needed profile DMs in %s (%s)", guild.name, guild.id)

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
        # Nudge admins to run the integrated setup flow
        lines.append("Welcome to Capy — let's get onboarded!")
        lines.append("Run `/server setup` to get started.")
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

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
            self.profile_helper: ProfileBatchHelper | None = ProfileBatchHelper()
        except Exception:
            self.profile_helper = None

    class CreateProfileView(discord.ui.View):
        """Persistent view with a button to launch the profile creation flow.

        Notes on persistence:
        - timeout=None makes the view persistent locally.
        - custom_id must be set on components for persistence across restarts.
        - Ensure `client.add_view(OnboardingManager.CreateProfileView())` is
          called on startup (e.g., in on_ready) so interactions are handled
          after bot restarts.
        """

        def __init__(self) -> None:
            # No timeout to allow the button to remain usable in DMs.
            super().__init__(timeout=None)

        @discord.ui.button(
            label="Create Your Profile",
            style=discord.ButtonStyle.primary,
            custom_id="onboarding:create_profile",
        )
        async def create_profile(self, interaction: discord.Interaction, _button: discord.ui.Button[object]) -> None:  # type: ignore[name-defined]
            # Route to the ProfileCog flow so it can present the modal ephemerally
            try:
                logger.info(
                    "onboarding: create_profile clicked by user=%s guild=%s",
                    interaction.user.id,
                    getattr(interaction.guild, "id", None),
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

    @staticmethod
    def register_persistent_views(client: discord.Client) -> None:
        """Register persistent views so component interactions survive restarts.

        Call this once on startup (e.g., in on_ready) to ensure the
        `CreateProfileView` handler is active for existing DM messages.
        """
        try:
            client.add_view(OnboardingManager.CreateProfileView())
            logger.info("onboarding: registered persistent CreateProfileView")
        except Exception as e:
            logger.error("onboarding: failed to register persistent views: %s", e)

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
                    interaction.user.id,
                    getattr(interaction.guild, "id", None),
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

                # Proactively disable the view on the original message to prevent double clicks
                try:
                    if interaction.message:
                        await interaction.message.edit(view=None)
                except Exception:
                    # Non-fatal; continue with setup
                    pass

                await cog.setup_flow(interaction)  # type: ignore[attr-defined]

                # After setup completes, attempt to delete the onboarding message
                try:
                    if interaction.message:
                        await interaction.message.delete()
                except Exception:
                    # Ignore if lacking permissions or message already gone
                    pass
            except Exception as e:
                logger.error("Failed to start server setup from onboarding: %s", e)
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "Something went wrong starting setup. Try /server setup.",
                        ephemeral=True,
                    )

    async def handle_guild_join(self, guild: discord.Guild) -> None:
        """Entry point for guild join onboarding. Orchestrates scan and messaging."""
        if not isinstance(guild, discord.Guild):
            return

        if not self._should_onboard(guild):
            return

        result = await self._perform_profile_scan(guild)
        if not result:
            return

        await self._act_on_scan_results(guild, result)

    def _should_onboard(self, guild: discord.Guild) -> bool:
        """Return True if onboarding should run for this guild; logs context."""
        self.logger.info(
            "onboarding: handle_guild_join guild=%s mode=%s require_manage=%s",
            guild.id,
            self.cfg.mode,
            self.cfg.require_manage_guild,
        )
        if not self.cfg.enabled or self.cfg.mode == "silent":
            self.logger.info("onboarding: disabled or silent; skipping intro")
            return False
        return True

    async def _perform_profile_scan(self, guild: discord.Guild):
        """Scan guild membership for profile presence; optionally DM owner on failure."""
        if not self.profile_helper:
            self.logger.error("onboarding: ProfileBatchHelper not available, cannot scan for profiles.")
            if self.cfg.mode == "dm":
                await self._try_dm_guild_owner(guild)
            return None
        try:
            result = await self.profile_helper.scan_profiles(guild)
            self.logger.info(
                "onboarding: scan complete with_profiles=%d without_profiles=%d",
                len(result.with_profiles),
                len(result.without_profiles),
            )
            return result
        except Exception as e:
            self.logger.error("onboarding: profile scan failed: %s", e)
            if self.cfg.mode == "dm":
                await self._try_dm_guild_owner(guild)
            return None

    async def _act_on_scan_results(self, guild: discord.Guild, result) -> None:
        """Take onboarding actions based on scan results and mode."""
        # Send DMs to members missing profiles (best effort)
        try:
            await self._dm_missing_profiles(guild, result.without_profiles)
        except Exception as e:
            self.logger.error("onboarding: failed sending profile creation DMs: %s", e)

        # DM owner if configured to do so
        if self.cfg.mode == "dm":
            await self._try_dm_guild_owner(guild)

        # Post intro announcement
        channel = await self._find_postable_channel(guild)
        if not channel:
            self.logger.warning(
                "No suitable channel found for onboarding in guild %s (%s)",
                guild.name,
                guild.id,
            )
            return
        await self._post_intro(channel, guild, len(result.without_profiles))

    async def _find_postable_channel(self, guild: discord.Guild) -> discord.abc.MessageableChannel | None:
        # 1) Prefer system channel if sendable
        if guild.system_channel and self._can_send(guild.system_channel):
            self.logger.debug("onboarding: using system channel %s for intro", guild.system_channel.id)
            return guild.system_channel

        # 2) If configured, try fallback channel id
        if self.cfg.fallback_channel_id:
            ch = guild.get_channel(self.cfg.fallback_channel_id)
            if isinstance(ch, discord.TextChannel) and self._can_send(ch):
                self.logger.debug("onboarding: using fallback channel %s for intro", ch.id)
                return ch

        # 3) First text channel we can send to
        for ch in guild.text_channels:
            if self._can_send(ch):
                self.logger.debug("onboarding: using first postable channel %s", ch.id)
                return ch
        self.logger.debug("onboarding: no postable channel found")
        return None

    def _can_send(self, channel: discord.TextChannel) -> bool:
        perms = channel.permissions_for(channel.guild.me)
        return bool(perms and perms.send_messages and perms.embed_links)

    async def _post_intro(self, channel: discord.TextChannel, guild: discord.Guild, missing_profiles: int) -> None:
        """Posts the introduction message to the given channel."""
        embed = discord.Embed(
            title=f"👋 Thanks for inviting me to {guild.name}!",
            description=self._build_intro_description(),
            color=discord.Color.blurple(),
        )

        if missing_profiles:
            embed.add_field(
                name="Get Everyone Set Up",
                value=(
                    f"It looks like about {missing_profiles} member(s) may still need a profile.\n"
                    "Use /profile to create or update your profile."
                ),
                inline=False,
            )

        view = self.SetupServerView(self.cfg.docs_url, self.cfg.require_manage_guild)

        try:
            await channel.send(embed=embed, view=view)
            self.logger.info("Posted onboarding intro to %s (%s)", guild.name, guild.id)
        except Exception as e:
            self.logger.error("Failed to post onboarding intro: %s", e)

    async def _dm_missing_profiles(self, guild: discord.Guild, without_profiles_ids: list[int]) -> None:
        """Direct-messages each human member without a profile with a create button."""
        if not without_profiles_ids:
            self.logger.info("onboarding: no members needed profile DMs in %s (%s)", guild.name, guild.id)
            return

        count = 0
        total_to_dm = len(without_profiles_ids)
        self.logger.info(
            "onboarding: DM pass starting for %d members without profiles in guild=%s",
            total_to_dm,
            guild.id,
        )

        # Rate limit: max 10 DMs per 10 seconds. Implemented as chunked sends
        # of size 10 followed by a 10s pause.
        chunk_size = 10
        cooldown_seconds = 10

        for i in range(0, len(without_profiles_ids), chunk_size):
            chunk = without_profiles_ids[i : i + chunk_size]
            for user_id in chunk:
                member = guild.get_member(user_id)
                if not member:
                    self.logger.debug("Could not find member with id %s in guild %s", user_id, guild.id)
                    continue

                try:
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
                    # Create a fresh view instance per DM so each message has an
                    # independent view object.
                    await dm.send(embed=embed, view=self.CreateProfileView())
                    count += 1
                except Exception as e:
                    self.logger.debug("Skipping DM to %s (%s): %s", member, getattr(member, "id", "?"), e)
                    continue

            # If there are more to send, sleep to enforce the windowed rate limit
            if i + chunk_size < len(without_profiles_ids):
                await asyncio.sleep(cooldown_seconds)

        if count:
            self.logger.info("onboarding: DM'd %d member(s) missing profiles in %s (%s)", count, guild.name, guild.id)
        else:
            self.logger.info(
                "onboarding: no members were successfully DM'd for profiles in %s (%s)", guild.name, guild.id
            )

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
        lines = [
            "Welcome to Capy — let's get onboarded!",
            "Run `/server setup` to get started.",
            self.cfg.message,
        ]
        if self.cfg.require_manage_guild:
            lines.append("\nOnly members with 'Manage Server' should configure settings.")
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

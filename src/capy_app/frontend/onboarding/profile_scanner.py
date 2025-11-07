"""Profile scanning and batching utilities for onboarding.

This helper is designed to scale: start with simple scanning, and evolve to
batched/background processing as member sizes grow.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from typing import TypeVar

import discord
from backend.db.database import Database
from backend.db.documents.guild import Guild
from backend.db.documents.user import User


@dataclass(slots=True)
class ProfileScanResult:
    with_profiles: list[int]
    without_profiles: list[int]


T = TypeVar("T")


class ProfileBatchHelper:
    """Helper to scan guild members for profile presence, optimized for scale.

    Current behavior:
    - Single bulk read of user IDs to determine which members have profiles
      (no per-member DB lookups).
    - Server-side bulk write using add_to_set to record the current guild on
      users who already have profiles (no reads, no duplicates).

    Future enhancements: chunked background processing for very large guilds,
    bounded concurrency for messaging, and caching.
    """

    def __init__(self, chunk_size: int = 100) -> None:
        self.chunk_size = max(1, chunk_size)
        self.logger = logging.getLogger("discord.onboarding.profile_scanner")

    async def scan_profiles(self, guild: discord.Guild) -> ProfileScanResult:
        """Scan members, update profile/guild links, and return results."""
        member_ids = self._get_human_member_ids(guild)
        with_profiles, without_profiles = self._split_by_profile_presence(member_ids)

        self.logger.info(
            "scan: %s (%s): %d with profiles, %d without",
            guild.name,
            guild.id,
            len(with_profiles),
            len(without_profiles),
        )

        if with_profiles:
            self._update_users_with_guild(with_profiles, int(guild.id))
            self._ensure_guild_and_update_users(guild, with_profiles)

        return ProfileScanResult(with_profiles=with_profiles, without_profiles=without_profiles)

    def _get_human_member_ids(self, guild: discord.Guild) -> list[int]:
        """Return IDs of non-bot members for a guild."""
        return [m.id for m in guild.members if not m.bot]

    def _split_by_profile_presence(self, member_ids: list[int]) -> tuple[list[int], list[int]]:
        """Split IDs into (with_profiles, without_profiles) via one DB query."""
        if not member_ids:
            return ([], [])
        id_list = Database.list_document_attr(User, "_id", {"pk__in": member_ids})
        existing_ids: set[int] = {int(x) for x in id_list}
        with_profiles = [mid for mid in member_ids if mid in existing_ids]
        without_profiles = [mid for mid in member_ids if mid not in existing_ids]
        return (with_profiles, without_profiles)

    def _update_users_with_guild(self, user_ids: list[int], guild_id: int) -> None:
        """Server-side add_to_set of guild_id into User.guilds for user_ids."""
        try:
            updated = Database.bulk_update_attr(User, user_ids, "guilds", guild_id)
            self.logger.info(
                "scan: updated %d user profile(s) with guild %s",
                int(updated),
                guild_id,
            )
        except Exception as e:
            self.logger.error("scan: failed updating users with guild %s: %s", guild_id, e)

    def _ensure_guild_and_update_users(self, guild: discord.Guild, user_ids: list[int]) -> None:
        """Ensure Guild doc exists, then merge user_ids into Guild.users uniquely."""
        gid = int(guild.id)
        try:
            guild_doc = Database.get_document(Guild, gid)
            if not guild_doc:
                guild_doc = Guild(_id=gid)
                Database.add_document(guild_doc)
                self.logger.info("scan: created guild doc for %s (%s)", guild.name, gid)

            existing_list = getattr(guild_doc, "users", []) or []
            existing_users = set(existing_list)
            to_add = [uid for uid in user_ids if uid not in existing_users]
            if not to_add:
                return

            merged_users = sorted(existing_users.union(user_ids))
            Database.update_document(guild_doc, {"users": merged_users})
            self.logger.info(
                "scan: added %d user(s) to guild %s users (now %d)",
                len(to_add),
                gid,
                len(merged_users),
            )
        except Exception as e:
            self.logger.error("scan: failed updating guild %s users: %s", gid, e)

    def _iter_chunks(self, items: list[T], size: int) -> Iterable[list[T]]:
        for i in range(0, len(items), size):
            yield items[i : i + size]

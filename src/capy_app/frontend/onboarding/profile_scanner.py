"""Profile scanning and batching utilities for onboarding.

This helper is designed to scale: start with simple scanning, and evolve to
batched/background processing as member sizes grow.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import TypeVar

import discord
from backend.db.database import Database
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

    async def scan_profiles(self, guild: discord.Guild) -> ProfileScanResult:
        """Scan all human members and split into with/without profile lists.

        Uses a single bulk ID lookup via Database to avoid N queries, then
        performs a server-side bulk add_to_set to ensure the current guild is
        present in user.guilds for all users with profiles.

        Returns lists of member IDs for downstream batching or messaging.
        """
        human_members: list[discord.Member] = [m for m in guild.members if not m.bot]
        member_ids: list[int] = [m.id for m in human_members]

        # Single fetch of existing user IDs via Database helper (minimal payload).
        id_list = Database.list_document_attr(User, "_id", {"pk__in": member_ids})
        existing_ids: set[int] = {int(x) for x in id_list}

        with_profiles: list[int] = []
        without_profiles: list[int] = []
        for mid in member_ids:
            if mid in existing_ids:
                with_profiles.append(mid)
            else:
                without_profiles.append(mid)

        # Server-side bulk add_to_set: no duplicates, no reads, all server-side.
        if with_profiles:
            Database.bulk_update_attr(User, with_profiles, "guilds", int(guild.id))

        return ProfileScanResult(with_profiles=with_profiles, without_profiles=without_profiles)

    def _iter_chunks(self, items: list[T], size: int) -> Iterable[list[T]]:
        for i in range(0, len(items), size):
            yield items[i : i + size]

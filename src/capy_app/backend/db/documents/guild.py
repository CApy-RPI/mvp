import datetime
import typing

import mongoengine
from backend.db.documents.restrict import RestrictedDocument, RestrictedEmbeddedDocument


class GuildChannels(RestrictedEmbeddedDocument):
    """Represents Discord channel configuration for a guild.

    Attributes:
        reports: Channel ID for report submissions
        announcements: Channel ID for announcements
        moderator: Channel ID for moderator communications
    """

    reports: int | None = mongoengine.IntField()
    announcements: int | None = mongoengine.IntField()
    moderator: int | None = mongoengine.IntField()


class GuildRoles(RestrictedEmbeddedDocument):
    """Represents role configuration for a guild.

    Attributes:
        visitor: Role identifier for visitors
        member: Role identifier for verified members
        eboard: Role identifier for executive board members
        admin: Role identifier for administrators
        office_hours: Role identifier for office hours
    """

    visitor: str | None = mongoengine.StringField()
    member: str | None = mongoengine.StringField()
    eboard: str | None = mongoengine.StringField()
    admin: str | None = mongoengine.StringField()
    advisor: str | None = mongoengine.StringField()
    office_hours: str | None = mongoengine.StringField()


class OfficeHours(RestrictedEmbeddedDocument):
    """Represents office hours schedule for a member.

    Attributes:
        name: Name of the person holding office hours
        schedule: Dictionary mapping weekdays to time slots
    """

    name: str = mongoengine.StringField(required=True)
    schedule: dict[str, list[str]] = mongoengine.DictField()


class Guild(RestrictedDocument):
    """Main guild document representing a Discord server configuration.

    Attributes:
        _id: Unique identifier for the guild
        users: List of user IDs belonging to the guild
        events: List of event IDs associated with the guild
        channels: Channel configuration for the guild
        roles: Role configuration for the guild
        created_at: Timestamp when the guild was created
        updated_at: Timestamp of last update
        office_hours: List of office hours schedules for members
    """

    _id: int = mongoengine.IntField(primary_key=True)
    users: list[int] = mongoengine.ListField(mongoengine.IntField())
    events: list[int] = mongoengine.ListField(mongoengine.IntField())
    channels: GuildChannels = mongoengine.EmbeddedDocumentField(
        GuildChannels, default=GuildChannels
    )
    roles: GuildRoles = mongoengine.EmbeddedDocumentField(GuildRoles, default=GuildRoles)
    office_hours: list[OfficeHours] = mongoengine.EmbeddedDocumentListField(
        OfficeHours, default=list
    )
    created_at: datetime.datetime = mongoengine.DateTimeField(default=datetime.datetime.now)
    updated_at: datetime.datetime = mongoengine.DateTimeField(default=datetime.datetime.now)

    meta = {"collection": "guilds", "indexes": ["created_at", "updated_at"]}

    def save(self, *args: typing.Any, **kwargs: typing.Any) -> "Guild":
        """Override save to update the updated_at timestamp."""
        self.updated_at = datetime.datetime.now()
        result = super().save(*args, **kwargs)
        return typing.cast("Guild", result)

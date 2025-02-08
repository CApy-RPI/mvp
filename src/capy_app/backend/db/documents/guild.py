import typing
import datetime
import mongoengine


class GuildChannels(mongoengine.EmbeddedDocument):
    """Represents Discord channel configuration for a guild.

    Attributes:
        reports: Channel ID for report submissions
        announcements: Channel ID for announcements
        moderator: Channel ID for moderator communications
    """

    reports: typing.Optional[int] = mongoengine.IntField()
    announcements: typing.Optional[int] = mongoengine.IntField()
    moderator: typing.Optional[int] = mongoengine.IntField()


class GuildRoles(mongoengine.EmbeddedDocument):
    """Represents role configuration for a guild.

    Attributes:
        eboard: Role identifier for executive board members
        admin: Role identifier for administrators
    """

    visitor: typing.Optional[str] = mongoengine.StringField()
    member: typing.Optional[str] = mongoengine.StringField()
    eboard: typing.Optional[str] = mongoengine.StringField()
    admin: typing.Optional[str] = mongoengine.StringField()


class Guild(mongoengine.Document):
    """Main guild document representing a Discord server configuration.

    Attributes:
        _id: Unique identifier for the guild
        users: List of user IDs belonging to the guild
        events: List of event IDs associated with the guild
        channels: Channel configuration for the guild
        roles: Role configuration for the guild
        created_at: Timestamp when the guild was created
        updated_at: Timestamp of last update
    """

    _id: int = mongoengine.IntField(primary_key=True)
    users: typing.List[int] = mongoengine.ListField(mongoengine.IntField())
    events: typing.List[int] = mongoengine.ListField(mongoengine.IntField())
    channels: GuildChannels = mongoengine.EmbeddedDocumentField(
        GuildChannels, default=GuildChannels
    )
    roles: GuildRoles = mongoengine.EmbeddedDocumentField(
        GuildRoles, default=GuildRoles
    )
    created_at: datetime.datetime = mongoengine.DateTimeField(
        default=datetime.datetime.utcnow
    )
    updated_at: datetime.datetime = mongoengine.DateTimeField(
        default=datetime.datetime.utcnow
    )

    meta = {"collection": "guilds", "indexes": ["created_at", "updated_at"]}

    def save(self, *args: typing.Any, **kwargs: typing.Any) -> "Guild":
        """Override save to update the updated_at timestamp."""
        self.updated_at = datetime.datetime.utcnow()
        result = super().save(*args, **kwargs)
        return typing.cast("Guild", result)

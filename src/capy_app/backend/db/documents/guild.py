import typing
import datetime
import mongoengine as me


class GuildChannels(me.EmbeddedDocument):
    """Represents Discord channel configuration for a guild.

    Attributes:
        reports: Channel ID for report submissions
        announcements: Channel ID for announcements
        moderator: Channel ID for moderator communications
    """

    reports: typing.Optional[int] = me.IntField()
    announcements: typing.Optional[int] = me.IntField()
    moderator: typing.Optional[int] = me.IntField()


class GuildRoles(me.EmbeddedDocument):
    """Represents role configuration for a guild.

    Attributes:
        eboard: Role identifier for executive board members
        admin: Role identifier for administrators
    """

    eboard: typing.Optional[str] = me.StringField()
    admin: typing.Optional[str] = me.StringField()


class Guild(me.Document):
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

    _id: int = me.IntField(primary_key=True)
    users: typing.List[int] = me.ListField(me.IntField())
    events: typing.List[int] = me.ListField(me.IntField())
    channels: GuildChannels = me.EmbeddedDocumentField(
        GuildChannels, default=GuildChannels
    )
    roles: GuildRoles = me.EmbeddedDocumentField(GuildRoles, default=GuildRoles)
    created_at: datetime.datetime = me.DateTimeField(default=datetime.datetime.utcnow)
    updated_at: datetime.datetime = me.DateTimeField(default=datetime.datetime.utcnow)

    meta = {"collection": "guilds", "indexes": ["created_at", "updated_at"]}

    def save(self, *args: typing.Any, **kwargs: typing.Any) -> "Guild":
        """Override save to update the updated_at timestamp."""
        self.updated_at = datetime.datetime.utcnow()
        result = super().save(*args, **kwargs)
        return typing.cast("Guild", result)

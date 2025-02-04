import typing
import datetime
import mongoengine as me


class EventReactions(me.EmbeddedDocument):
    """Tracks reaction counts for an event.

    Attributes:
        yes: Count of positive responses
        maybe: Count of uncertain responses
        no: Count of negative responses
    """

    yes: int = me.IntField(default=0)
    maybe: int = me.IntField(default=0)
    no: int = me.IntField(default=0)


class EventDetails(me.EmbeddedDocument):
    """Stores detailed information about an event.

    Attributes:
        name: Title of the event
        time: Date and time when the event occurs
        location: Physical or virtual location
        description: Detailed event description
        reactions: Tracking of user reactions
    """

    name: str = me.StringField(required=True)
    time: datetime.datetime = me.DateTimeField(required=True)
    location: typing.Optional[str] = me.StringField()
    description: typing.Optional[str] = me.StringField()
    reactions: EventReactions = me.EmbeddedDocumentField(
        EventReactions, default=EventReactions
    )


class Event(me.Document):
    """Main event document storing event data and relationships.

    Attributes:
        _id: Unique identifier for the event
        users: List of user IDs attending the event
        guild_id: ID of the hosting guild
        message_id: Discord message ID for the event
        details: Detailed event information
        created_at: Timestamp when the event was created
        updated_at: Timestamp of last update
    """

    _id: int = me.IntField(primary_key=True)
    users: typing.List[int] = me.ListField(me.IntField())
    guild_id: int = me.IntField()
    message_id: int = me.IntField()
    details: EventDetails = me.EmbeddedDocumentField(EventDetails, required=True)
    created_at: datetime.datetime = me.DateTimeField(default=datetime.datetime.utcnow)
    updated_at: datetime.datetime = me.DateTimeField(default=datetime.datetime.utcnow)

    meta = {"collection": "events", "indexes": ["created_at", "updated_at"]}

    def save(self, *args: typing.Any, **kwargs: typing.Any) -> "Event":
        """Override save to update the updated_at timestamp."""
        self.updated_at = datetime.datetime.utcnow()
        result = super().save(*args, **kwargs)
        return typing.cast("Event", result)

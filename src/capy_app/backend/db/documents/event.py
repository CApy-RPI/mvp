import typing
import datetime
import mongoengine


class EventReactions(mongoengine.EmbeddedDocument):
    """Tracks reaction counts for an event.

    Attributes:
        yes: Count of positive responses
        maybe: Count of uncertain responses
        no: Count of negative responses
    """

    yes: int = mongoengine.IntField(default=0)
    maybe: int = mongoengine.IntField(default=0)
    no: int = mongoengine.IntField(default=0)


class EventDetails(mongoengine.EmbeddedDocument):
    """Stores detailed information about an event.

    Attributes:
        name: Title of the event
        time: Date and time when the event occurs
        location: Physical or virtual location
        description: Detailed event description
        reactions: Tracking of user reactions
    """

    name: str = mongoengine.StringField(required=True)
    time: datetime.datetime = mongoengine.DateTimeField(required=True)
    location: typing.Optional[str] = mongoengine.StringField()
    description: typing.Optional[str] = mongoengine.StringField()
    reactions: EventReactions = mongoengine.EmbeddedDocumentField(
        EventReactions, default=EventReactions
    )


class Event(mongoengine.Document):
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

    _id: int = mongoengine.IntField(primary_key=True)
    users: typing.List[int] = mongoengine.ListField(mongoengine.IntField())
    guild_id: int = mongoengine.IntField()
    message_id: int = mongoengine.IntField()
    details: EventDetails = mongoengine.EmbeddedDocumentField(
        EventDetails, required=True
    )
    created_at: datetime.datetime = mongoengine.DateTimeField(
        default=datetime.datetime.now
    )
    updated_at: datetime.datetime = mongoengine.DateTimeField(
        default=datetime.datetime.now
    )

    meta = {"collection": "events", "indexes": ["created_at", "updated_at"]}

    def save(self, *args: typing.Any, **kwargs: typing.Any) -> "Event":
        """Override save to update the updated_at timestamp."""
        self.updated_at = datetime.datetime.now()
        result = super().save(*args, **kwargs)
        return typing.cast("Event", result)

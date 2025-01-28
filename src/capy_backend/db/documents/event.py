import mongoengine as me


class EventReactions(me.EmbeddedDocument):
    """
    A class to represent reactions to an event.
    
    Attributes:
        yes (int): The number of 'yes' reactions.
        maybe (int): The number of 'maybe' reactions.
        no (int): The number of 'no' reactions.
    """
    yes = me.IntField(default=0)
    maybe = me.IntField(default=0)
    no = me.IntField(default=0)


class EventDetails(me.EmbeddedDocument):
    """
    A class to represent the details of an event.
    
    Attributes:
        name (str): The name of the event.
        datetime (datetime): The date and time of the event.
        location (str): The location of the event.
        description (str): The description of the event.
        reactions (EventReactions): The reactions to the event.
    """
    name = me.StringField(required=True)
    datetime = me.DateTimeField(required=True)
    location = me.StringField()
    description = me.StringField()
    reactions = me.EmbeddedDocumentField(EventReactions, default=EventReactions)


class Event(me.Document):
    """
    A class to represent an event.
    
    Attributes:
        _id (int): The primary key of the event.
        users (List[int]): The list of user IDs attending the event.
        guild_id (int): The ID of the guild hosting the event.
        message_id (int): The ID of the message associated with the event.
        details (EventDetails): The details of the event.
    """
    _id = me.IntField(primary_key=True)
    users = me.ListField(me.IntField())
    guild_id = me.IntField()
    message_id = me.IntField()
    details = me.EmbeddedDocumentField(EventDetails, required=True)

    meta = {"collection": "event"}

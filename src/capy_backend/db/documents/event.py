import mongoengine as me


class EventReactions(me.EmbeddedDocument):
    yes = me.IntField(default=0)
    maybe = me.IntField(default=0)
    no = me.IntField(default=0)


class EventDetails(me.EmbeddedDocument):
    name = me.StringField(required=True)
    datetime = me.DateTimeField(required=True)
    location = me.StringField()
    description = me.StringField()
    reactions = me.EmbeddedDocumentField(EventReactions, default=EventReactions)


class Event(me.Document):
    _id = me.IntField(primary_key=True)
    users = me.ListField(me.IntField())
    guild_id = me.IntField()
    message_id = me.IntField()
    details = me.EmbeddedDocumentField(EventDetails, required=True)

    meta = {"collection": "event"}

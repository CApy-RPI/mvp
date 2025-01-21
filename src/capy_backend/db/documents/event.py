from datetime import datetime
import mongoengine as me

from .restricted import RestrictedDocument, RestrictedEmbeddedDocument


class EventReactions(RestrictedEmbeddedDocument):
    yes = me.IntField(default=0)
    maybe = me.IntField(default=0)
    no = me.IntField(default=0)


class EventDetails(RestrictedEmbeddedDocument):
    name = me.StringField(required=True)
    datetime = me.DateTimeField(required=True)
    location = me.StringField()
    description = me.StringField()
    reactions = me.EmbeddedDocumentField(EventReactions, default=EventReactions)


class Event(RestrictedDocument):
    users = me.ListField(me.IntField())
    guild_id = me.IntField()
    message_id = me.IntField()
    details = me.EmbeddedDocumentField(EventDetails, required=True)

    meta = {**RestrictedDocument.meta, "collection": "event"}

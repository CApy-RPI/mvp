from datetime import datetime
import mongoengine as me

from .restricted import RestrictedDocument, RestrictedEmbeddedDocument


class EventReactions(RestrictedEmbeddedDocument):
    yes = me.IntField(default=0)
    maybe = me.IntField(default=0)
    no = me.IntField(default=0)


class UserEventResponse(RestrictedEmbeddedDocument):
    user_id = me.IntField(required=True)
    response = me.StringField(choices=['yes', 'no', 'maybe'], required=True)


class EventDetails(RestrictedEmbeddedDocument):
    name = me.StringField(required=True)
    datetime = me.DateTimeField(required=True)
    location = me.StringField()
    description = me.StringField()
    reactions = me.EmbeddedDocumentField(EventReactions, default=EventReactions)
    user_responses = me.ListField(me.EmbeddedDocumentField(UserEventResponse))
    status = me.StringField(choices=['upcoming', 'ongoing', 'passed'], default='upcoming')


class Event(RestrictedDocument):
    users = me.ListField(me.IntField())
    guild_id = me.IntField()
    message_id = me.IntField()
    details = me.EmbeddedDocumentField(EventDetails, required=True)

    meta = {**RestrictedDocument.meta, "collection": "event"}

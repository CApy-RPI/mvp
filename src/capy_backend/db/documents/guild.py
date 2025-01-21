import mongoengine as me

from .restricted import RestrictedDocument, RestrictedEmbeddedDocument


class GuildChannels(RestrictedEmbeddedDocument):
    reports = me.IntField()
    announcements = me.IntField()
    moderator = me.IntField()


class GuildRoles(RestrictedEmbeddedDocument):
    eboard = me.StringField()
    admin = me.StringField()


class Guild(RestrictedDocument):
    users = me.ListField(me.IntField())
    events = me.ListField(me.IntField())
    channels = me.kEmbeddedDocumentField(GuildChannels, default=GuildChannels)
    roles = me.EmbeddedDocumentField(GuildRoles, default=GuildRoles)

    meta = {**RestrictedDocument.meta, "collection": "guilds"}

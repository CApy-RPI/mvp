import mongoengine as me


class GuildChannels(me.EmbeddedDocument):
    reports = me.IntField()
    announcements = me.IntField()
    moderator = me.IntField()


class GuildRoles(me.EmbeddedDocument):
    eboard = me.StringField()
    admin = me.StringField()


class Guild(me.Document):
    _id = me.IntField(primary_key=True)
    users = me.ListField(me.IntField())
    events = me.ListField(me.IntField())
    channels = me.EmbeddedDocumentField(GuildChannels, default=GuildChannels)
    roles = me.EmbeddedDocumentField(GuildRoles, default=GuildRoles)

    meta = {"collection": "guilds"}

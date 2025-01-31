import mongoengine as me


class GuildChannels(me.EmbeddedDocument):
    """
    A class to represent the channels of a guild.

    Attributes:
        reports (int): The ID of the reports channel.
        announcements (int): The ID of the announcements channel.
        moderator (int): The ID of the moderator channel.
    """

    reports = me.IntField()
    announcements = me.IntField()
    moderator = me.IntField()


class GuildRoles(me.EmbeddedDocument):
    """
    A class to represent the roles of a guild.

    Attributes:
        eboard (str): The role of the eboard.
        admin (str): The role of the admin.
    """

    eboard = me.StringField()
    admin = me.StringField()


class Guild(me.Document):
    """
    A class to represent a guild.

    Attributes:
        _id (int): The primary key of the guild.
        users (List[int]): The list of user IDs in the guild.
        events (List[int]): The list of event IDs associated with the guild.
        channels (GuildChannels): The channels of the guild.
        roles (GuildRoles): The roles of the guild.
    """

    _id = me.IntField(primary_key=True)
    users = me.ListField(me.IntField())
    events = me.ListField(me.IntField())
    channels = me.EmbeddedDocumentField(GuildChannels, default=GuildChannels)
    roles = me.EmbeddedDocumentField(GuildRoles, default=GuildRoles)

    meta = {"collection": "guilds"}

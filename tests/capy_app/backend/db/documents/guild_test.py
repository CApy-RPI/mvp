import mongoengine
import pytest
from mongomock import MongoClient

from capy_app.backend.db.documents.guild import Guild, GuildChannels, GuildRoles

REPORTS_CHANNEL_ID = 111
ANNOUNCEMENTS_CHANNEL_ID = 222
MODERATOR_CHANNEL_ID = 333
USER_ID = 105
EVENT_ID = 205


@pytest.fixture(scope="module")
def db():
    """
    Set up a mock MongoDB instance for testing using mongomock.
    """
    mongoengine.connect(
        db="test_guild_db",
        alias="default",
        mongo_client_class=MongoClient,
        uuidRepresentation="standard",
    )
    yield
    mongoengine.disconnect(alias="default")


@pytest.fixture(autouse=True)
def clean_db():
    """
    Clean up the database before each test.
    """
    db_instance = mongoengine.get_db("default")
    for collection_name in db_instance.list_collection_names():
        db_instance.drop_collection(collection_name)


def test_create_guild_defaults(_db):
    guild = Guild(_id=1, users=[101, 102], events=[201, 202])
    guild.save()

    saved_guild = Guild.objects.get(_id=1)
    assert saved_guild._id == 1
    assert saved_guild.users == [101, 102]
    assert saved_guild.events == [201, 202]
    assert isinstance(saved_guild.channels, GuildChannels)
    assert isinstance(saved_guild.roles, GuildRoles)


def test_create_guild_custom_channels(_db):
    custom_channels = GuildChannels(reports=123, announcements=456, moderator=789)
    guild = Guild(_id=2, users=[103], events=[203], channels=custom_channels)
    guild.save()

    saved_guild = Guild.objects.get(_id=2)
    assert saved_guild.channels.reports == REPORTS_CHANNEL_ID
    assert saved_guild.channels.announcements == ANNOUNCEMENTS_CHANNEL_ID
    assert saved_guild.channels.moderator == MODERATOR_CHANNEL_ID


def test_create_guild_custom_roles(_db):
    custom_roles = GuildRoles(eboard="President", admin="AdminRole")
    guild = Guild(_id=3, users=[104], events=[204], roles=custom_roles)
    guild.save()

    saved_guild = Guild.objects.get(_id=3)
    assert saved_guild.roles.eboard == "President"
    assert saved_guild.roles.admin == "AdminRole"


def test_add_users_and_events(_db):
    guild = Guild(_id=4, users=[], events=[])
    guild.save()

    # Update users and events
    guild.update(push__users=105, push__events=205)
    updated_guild = Guild.objects.get(_id=4)
    assert USER_ID in updated_guild.users
    assert EVENT_ID in updated_guild.events


def test_update_channels_roles(_db):
    guild = Guild(_id=5, users=[106], events=[206])
    guild.save()

    # Update channels and roles
    guild.update(
        set__channels=GuildChannels(reports=111, announcements=222, moderator=333),
        set__roles=GuildRoles(eboard="VicePresident", admin="ModeratorRole"),
    )
    updated_guild = Guild.objects.get(_id=5)
    assert updated_guild.channels.reports == REPORTS_CHANNEL_ID
    assert updated_guild.channels.announcements == ANNOUNCEMENTS_CHANNEL_ID
    assert updated_guild.channels.moderator == MODERATOR_CHANNEL_ID
    assert updated_guild.roles.eboard == "VicePresident"
    assert updated_guild.roles.admin == "ModeratorRole"

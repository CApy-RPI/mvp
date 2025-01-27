import pytest
import mongoengine
from src.capy_backend.db.documents.guild import Guild, GuildChannels, GuildRoles

@pytest.fixture(scope="module")
def db():
    """
    Create a temporary in-memory test database using mongoengine + mongomock.
    If you prefer a real MongoDB instance, remove 'mongomock://'.
    """
    mongoengine.connect('test_guild_db', host='mongomock://localhost')
    yield
    mongoengine.disconnect()


def test_create_guild_defaults(db):
    """
    Test creating a Guild with no arguments other than defaults
    and ensure embedded documents have default objects with None fields.
    """
    guild = Guild().save()

    saved_guild = Guild.objects().first()
    assert saved_guild is not None, "Guild should be saved and retrievable"

    # By default, these are empty lists
    assert saved_guild.users == []
    assert saved_guild.events == []

    # Check that channels and roles are auto-created (default=GuildChannels, GuildRoles)
    assert saved_guild.channels is not None, "Channels should not be None by default"
    assert saved_guild.roles is not None, "Roles should not be None by default"

    # IntFields in GuildChannels should be None if not set
    assert saved_guild.channels.reports is None
    assert saved_guild.channels.announcements is None
    assert saved_guild.channels.moderator is None

    # StringFields in GuildRoles should be None if not set
    assert saved_guild.roles.eboard is None
    assert saved_guild.roles.admin is None


def test_create_guild_custom_channels(db):
    """
    Test providing custom channel IDs for GuildChannels.
    """
    channels = GuildChannels(
        reports=1001,
        announcements=1002,
        moderator=1003,
    )
    guild = Guild(channels=channels).save()

    saved_guild = Guild.objects().first()
    assert saved_guild.channels.reports == 1001
    assert saved_guild.channels.announcements == 1002
    assert saved_guild.channels.moderator == 1003


def test_create_guild_custom_roles(db):
    """
    Test providing custom role names for GuildRoles.
    """
    roles = GuildRoles(
        eboard="ExecutiveBoardRole",
        admin="AdminRole",
    )
    guild = Guild(roles=roles).save()

    saved_guild = Guild.objects().first()
    assert saved_guild.roles.eboard == "ExecutiveBoardRole"
    assert saved_guild.roles.admin == "AdminRole"


def test_add_users_and_events(db):
    """
    Test adding users and events lists to the Guild.
    """
    guild = Guild(
        users=[123, 456],
        events=[111, 222]
    ).save()

    saved_guild = Guild.objects().first()
    assert saved_guild.users == [123, 456]
    assert saved_guild.events == [111, 222]

    # Now update the guild and add more entries
    saved_guild.users.append(789)
    saved_guild.events.append(333)
    saved_guild.save()

    updated_guild = Guild.objects().first()
    assert updated_guild.users == [123, 456, 789]
    assert updated_guild.events == [111, 222, 333]


def test_update_channels_roles(db):
    """
    Test updating existing channel and role fields.
    """
    guild = Guild().save()

    # Update the channels and roles
    guild.channels.reports = 5555
    guild.channels.announcements = 6666
    guild.roles.eboard = "EboardUpdated"

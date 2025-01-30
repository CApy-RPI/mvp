import unittest
import mongoengine
from mongomock import MongoClient
from src.capy_app.backend.db.documents.guild import Guild, GuildChannels, GuildRoles


class TestGuild(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """
        Set up a mock MongoDB instance for all tests in this class using mongomock.
        """
        cls.mongo_client = MongoClient()  # Create a mongomock instance
        mongoengine.connect(
            db="test_guild_db",
            alias="default",
            mongo_client_class=MongoClient
        )

    @classmethod
    def tearDownClass(cls):
        """
        Disconnect from the mock MongoDB instance.
        """
        mongoengine.disconnect(alias="default")

    def setUp(self):
        """
        Clean up the database before each test.
        """
        db = self.mongo_client["test_guild_db"]
        for collection_name in db.list_collection_names():
            db.drop_collection(collection_name)

    def test_create_guild_defaults(self):
        guild = Guild(
            _id=1,
            users=[101, 102],
            events=[201, 202]
        )
        guild.save()

        saved_guild = Guild.objects.get(_id=1)
        self.assertEqual(saved_guild._id, 1)
        self.assertEqual(saved_guild.users, [101, 102])
        self.assertEqual(saved_guild.events, [201, 202])
        self.assertIsInstance(saved_guild.channels, GuildChannels)
        self.assertIsInstance(saved_guild.roles, GuildRoles)

    def test_create_guild_custom_channels(self):
        custom_channels = GuildChannels(reports=123, announcements=456, moderator=789)
        guild = Guild(
            _id=2,
            users=[103],
            events=[203],
            channels=custom_channels
        )
        guild.save()

        saved_guild = Guild.objects.get(_id=2)
        self.assertEqual(saved_guild.channels.reports, 123)
        self.assertEqual(saved_guild.channels.announcements, 456)
        self.assertEqual(saved_guild.channels.moderator, 789)

    def test_create_guild_custom_roles(self):
        custom_roles = GuildRoles(eboard="President", admin="AdminRole")
        guild = Guild(
            _id=3,
            users=[104],
            events=[204],
            roles=custom_roles
        )
        guild.save()

        saved_guild = Guild.objects.get(_id=3)
        self.assertEqual(saved_guild.roles.eboard, "President")
        self.assertEqual(saved_guild.roles.admin, "AdminRole")

    def test_add_users_and_events(self):
        guild = Guild(
            _id=4,
            users=[],
            events=[]
        )
        guild.save()

        # Update users and events
        guild.update(push__users=105, push__events=205)
        updated_guild = Guild.objects.get(_id=4)
        self.assertIn(105, updated_guild.users)
        self.assertIn(205, updated_guild.events)

    def test_update_channels_roles(self):
        guild = Guild(
            _id=5,
            users=[106],
            events=[206]
        )
        guild.save()

        # Update channels and roles
        guild.update(
            set__channels=GuildChannels(reports=111, announcements=222, moderator=333),
            set__roles=GuildRoles(eboard="VicePresident", admin="ModeratorRole")
        )
        updated_guild = Guild.objects.get(_id=5)
        self.assertEqual(updated_guild.channels.reports, 111)
        self.assertEqual(updated_guild.channels.announcements, 222)
        self.assertEqual(updated_guild.channels.moderator, 333)
        self.assertEqual(updated_guild.roles.eboard, "VicePresident")
        self.assertEqual(updated_guild.roles.admin, "ModeratorRole")


if __name__ == "__main__":
    unittest.main()

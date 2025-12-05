# third-party imports
import datetime

import mongomock
import pytest
from mongoengine import connect, disconnect

# local imports
from capy_app.backend.db.database import Database
from capy_app.backend.db.documents.user import User, UserName, UserProfile


@pytest.fixture(scope="module")
def db():
    disconnect()  # Ensure any existing connections are disconnected
    connect(
        "mongoenginetest",
        host="mongodb://localhost",
        mongo_client_class=mongomock.MongoClient,
        uuidRepresentation="standard",
    )
    db_instance = Database()
    yield db_instance
    disconnect()


@pytest.fixture
def user():
    return User(
        _id=1,
        profile=UserProfile(
            name=UserName(first="John", last="Doe"),
            school_email="john.doe@example.com",
            student_id=123456,
            major="Computer Science",
            graduation_year=2024,
            phone=1234567890,
        ),
    )


@pytest.fixture
def user2():
    return User(
        _id=2,
        profile=UserProfile(
            name=UserName(first="Jane", last="Smith"),
            school_email="jane.smith@example.com",
            student_id=654321,
            major="Mathematics",
            graduation_year=2023,
            phone=9876543210,
        ),
    )


@pytest.fixture(autouse=True)
def clean_db():
    yield
    User.drop_collection()


def test_add_user(db, user):
    db.add_document(user)
    fetched_user = db.get_document(User, 1)
    assert fetched_user is not None


def test_get_user(db, user):
    db.add_document(user)
    fetched_user = db.get_document(User, 1)
    assert fetched_user.profile.name.first == "John"


def test_update_user(db, user):
    db.add_document(user)
    updates = {"profile__name__first": "Jane"}
    assert user.profile.name.first == "John"
    updated_user = db.update_document(user, updates)
    assert updated_user.profile.name.first == "Jane"
    updated_user = db.get_document(User, 1)
    assert updated_user.profile.name.first == "Jane"


def test_delete_user(db, user):
    db.add_document(user)
    db.delete_document(user)
    fetched_user = db.get_document(User, 1)
    assert fetched_user is None


def test_delete_user_by_id(db, user):
    db.add_document(user)
    db.delete_document_by_id(User, 1)
    fetched_user = db.get_document(User, 1)
    assert fetched_user is None


def test_list_users(db, user, user2):
    db.add_document(user)
    db.add_document(user2)
    users = db.list_documents(User)
    expected_user_count = 2
    assert len(users) == expected_user_count


def test_list_user_ids_bulk_read(db, user, user2):
    # Arrange: add two users
    db.add_document(user)
    db.add_document(user2)

    # Act: fetch IDs using the minimal payload helper
    ids = Database.list_document_attr(User, "_id", {"pk__in": [1, 2, 3]})

    # Assert: only existing IDs are returned
    assert set(ids) == {1, 2}


def test_get_and_set_attributes(db, user):
    db.add_document(user)
    fetched_user = db.get_document(User, 1)
    assert fetched_user.profile.name.first == "John"
    db.update_document(fetched_user, {"profile__name__first": "Jane"})
    updated_user = db.get_document(User, 1)
    assert updated_user.profile.name.first == "Jane"


def test_get_and_set_embedded_attributes(db, user):
    db.add_document(user)
    fetched_user = db.get_document(User, 1)
    assert fetched_user.profile.name.first == "John"
    fetched_user.profile.name.middle = "B"
    db.update_document(fetched_user, {"profile__name__middle": "B"})
    updated_user = db.get_document(User, 1)
    assert updated_user.profile.name.middle == "B"


def test_bulk_update_attr_append_list(db, user, user2):
    # Arrange: two users with empty guilds
    db.add_document(user)
    db.add_document(user2)
    assert db.get_document(User, 1).guilds == []
    assert db.get_document(User, 2).guilds == []

    # Act: append guild id 100 to both
    updated = Database.bulk_update_attr(User, [1, 2], "guilds", 100)

    # Assert
    assert updated == 2  # noqa: PLR2004
    assert db.get_document(User, 1).guilds == [100]
    assert db.get_document(User, 2).guilds == [100]

    # Appending again should not duplicate due to add_to_set
    updated_again = Database.bulk_update_attr(User, [1, 2], "guilds", 100)
    assert updated_again in (
        0,
        2,
    )  # depending on backend it may count matched vs modified
    assert db.get_document(User, 1).guilds == [100]
    assert db.get_document(User, 2).guilds == [100]


def test_bulk_update_attr_set_scalar(db, user, user2):
    # Arrange
    db.add_document(user)
    db.add_document(user2)
    ts = datetime.datetime(2020, 1, 1)

    # Act: set created_at for both (scalar field)
    updated = Database.bulk_update_attr(User, [1, 2], "created_at", ts)

    # Assert
    assert updated == 2  # noqa: PLR2004
    assert db.get_document(User, 1).created_at == ts
    assert db.get_document(User, 2).created_at == ts

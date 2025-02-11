import pytest
from mongoengine import connect, disconnect
import mongomock

from src.capy_app.backend.db.database import Database
from src.capy_app.backend.db.documents.user import User, UserProfile, UserName


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
            major=["Computer Science"],
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
            major=["Mathematics"],
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


def test_list_users(db, user, user2):
    db.add_document(user)
    db.add_document(user2)
    users = db.list_documents(User)
    assert len(users) == 2


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

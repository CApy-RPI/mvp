import pytest
import mongoengine
import mongomock
from datetime import datetime

from src.capy_app.backend.db.documents.event import Event, EventDetails, EventReactions


@pytest.fixture(scope="module")
def db():
    """
    Connect to an in-memory MongoDB test database using mongomock,
    as required by newer versions of mongoengine (>= 0.27).
    """
    mongoengine.connect(
        db="test_event_db",
        alias="default",
        mongo_client_class=mongomock.MongoClient,
        uuidRepresentation="standard",
    )
    yield
    mongoengine.disconnect()


def test_event_creation(db):
    """
    Create an Event with a custom primary key (_id).
    If your Event model defines an auto _id, you can omit _id=123.
    """
    details = EventDetails(
        name="Test Event",
        datetime=datetime(2025, 1, 1, 12, 0),
    )

    event = Event(
        _id=123,  # or any unique value
        users=[123, 456],
        guild_id=789,
        message_id=111,
        details=details,
    )
    event.save()

    saved_event = Event.objects(_id=123).first()
    assert saved_event is not None
    assert saved_event.details.name == "Test Event"
    assert saved_event.details.datetime == datetime(2025, 1, 1, 12, 0)
    assert saved_event.users == [123, 456]
    assert saved_event.guild_id == 789
    assert saved_event.message_id == 111


def test_event_reactions_defaults(db):
    # If your Event requires an _id, specify it:
    details = EventDetails(
        name="Event With Reactions", datetime=datetime(2030, 5, 5, 10, 0)
    )
    event = Event(_id=200, details=details).save()

    retrieved = Event.objects(_id=200).first()
    assert retrieved.details.reactions.yes == 0
    assert retrieved.details.reactions.maybe == 0
    assert retrieved.details.reactions.no == 0


def test_event_required_name(db):
    """
    Test that 'name' is required in EventDetails.
    """
    from mongoengine import ValidationError

    details = EventDetails(
        # missing name
        datetime=datetime(2025, 1, 1, 12, 0),
    )
    event = Event(_id=201, details=details)

    with pytest.raises(ValidationError) as excinfo:
        event.save()
    assert "Field is required" in str(excinfo.value)
    assert "name" in str(excinfo.value)


def test_event_required_datetime(db):
    """
    Test that 'datetime' is required in EventDetails.
    """
    from mongoengine import ValidationError

    details = EventDetails(
        name="Event Missing Date"
        # missing datetime
    )
    event = Event(_id=202, details=details)

    with pytest.raises(ValidationError) as excinfo:
        event.save()
    assert "Field is required" in str(excinfo.value)
    assert "datetime" in str(excinfo.value)


def test_add_users_after_creation(db):
    details = EventDetails(name="Event to Update", datetime=datetime(2025, 1, 1, 12, 0))
    event = Event(_id=203, users=[111], guild_id=222, message_id=333, details=details)
    event.save()

    event.users.append(444)
    event.save()

    retrieved = Event.objects(_id=203).first()
    assert retrieved.users == [111, 444]


def test_set_reactions(db):
    reactions = EventReactions(yes=10, maybe=2, no=1)
    details = EventDetails(
        name="Event With Custom Reactions",
        datetime=datetime(2030, 6, 6, 12, 0),
        reactions=reactions,
    )
    Event(_id=204, details=details).save()

    event = Event.objects(_id=204).first()
    assert event.details.reactions.yes == 10
    assert event.details.reactions.maybe == 2
    assert event.details.reactions.no == 1

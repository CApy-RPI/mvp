from datetime import datetime

import mongoengine
import mongomock
import pytest

from capy_app.backend.db.documents.event import Event, EventDetails, EventReactions

REACTIONS_YES = 5
REACTIONS_MAYBE = 3
REACTIONS_NO = 2


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
    details = EventDetails(
        name="Test Event",
        time=datetime(2025, 1, 1, 12, 0),
        location="Zoom",
        description="Testing event creation",
    )

    event = Event(
        _id=123,
        yes_users=[101],
        maybe_users=[102],
        no_users=[],
        guild_id=789,
        message_id=111,
        details=details,
    )
    event.save()

    saved_event = Event.objects(_id=123).first()
    assert saved_event is not None
    assert saved_event.details.name == "Test Event"
    assert saved_event.details.time == datetime(2025, 1, 1, 12, 0)
    assert saved_event.yes_users == [101]
    assert saved_event.maybe_users == [102]
    assert saved_event.no_users == []
    assert saved_event.guild_id == 789
    assert saved_event.message_id == 111


def test_event_reactions_defaults(db):
    details = EventDetails(name="Event With Reactions", time=datetime(2030, 5, 5, 10, 0))

    Event(_id=200, details=details).save()

    retrieved = Event.objects(_id=200).first()
    assert retrieved.details.reactions.yes == 0
    assert retrieved.details.reactions.maybe == 0
    assert retrieved.details.reactions.no == 0


def test_event_required_name(db):
    from mongoengine import ValidationError

    details = EventDetails(
        # name missing
        time=datetime(2025, 1, 1, 12, 0)
    )
    event = Event(_id=201, details=details)

    with pytest.raises(ValidationError) as excinfo:
        event.save()

    assert "Field is required" in str(excinfo.value)
    assert "name" in str(excinfo.value)


def test_event_required_time(db):
    from mongoengine import ValidationError

    details = EventDetails(
        name="Missing Time"
        # time missing
    )
    event = Event(_id=202, details=details)

    with pytest.raises(ValidationError) as excinfo:
        event.save()

    assert "Field is required" in str(excinfo.value)
    assert "time" in str(excinfo.value)


def test_add_users_after_creation(db):
    details = EventDetails(name="Modifiable Event", time=datetime(2025, 1, 1, 12, 0))
    event = Event(
        _id=203,
        yes_users=[111],
        maybe_users=[],
        no_users=[],
        guild_id=222,
        message_id=333,
        details=details,
    )
    event.save()

    event.yes_users.append(444)
    event.save()

    retrieved = Event.objects(_id=203).first()
    assert retrieved.yes_users == [111, 444]


def test_set_reactions_explicitly(db):
    reactions = EventReactions(yes=5, maybe=3, no=2)
    details = EventDetails(
        name="Custom Reactions", time=datetime(2031, 6, 6, 15, 0), reactions=reactions
    )

    Event(_id=204, details=details).save()

    event = Event.objects(_id=204).first()
    assert event.details.reactions.yes == REACTIONS_YES
    assert event.details.reactions.maybe == REACTIONS_MAYBE
    assert event.details.reactions.no == REACTIONS_NO

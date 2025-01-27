import pytest
import mongoengine
from datetime import datetime

# Adjust these imports to match your actual module structure
from src.capy_backend.db.documents.event import Event, EventDetails, EventReactions


@pytest.fixture(scope="module")
def db():
    """
    Create a temporary in-memory test database using mongoengine.
    The in-memory option is only available for the 'mongomock' engine.
    If you're connecting to a real MongoDB instance, replace accordingly.
    """
    mongoengine.connect('test_event_db', host='mongomock://localhost')
    yield
    mongoengine.disconnect()


def test_event_creation(db):
    """
    Test creating a simple event with minimal required fields.
    """

    # Prepare data
    details = EventDetails(
        name="Test Event",
        datetime=datetime(2025, 1, 1, 12, 0),  # just an example
    )

    event = Event(
        users=[123, 456],
        guild_id=789,
        message_id=111,
        details=details
    )

    # Save event
    event.save()

    # Retrieve event from DB
    saved_event = Event.objects().first()

    assert saved_event is not None, "Event should be saved and retrievable"
    assert saved_event.details.name == "Test Event"
    assert saved_event.details.datetime == datetime(2025, 1, 1, 12, 0)
    assert saved_event.users == [123, 456]
    assert saved_event.guild_id == 789
    assert saved_event.message_id == 111


def test_event_reactions_defaults(db):
    """
    Test that EventReactions defaults to 0 for yes, maybe, no.
    """

    details = EventDetails(
        name="Event With Reactions",
        datetime=datetime(2030, 5, 5, 10, 0)
    )
    event = Event(details=details).save()

    retrieved = Event.objects().first()
    # Test that the embedded reactions fields have default values (0)
    assert retrieved.details.reactions.yes == 0
    assert retrieved.details.reactions.maybe == 0
    assert retrieved.details.reactions.no == 0


def test_event_required_name(db):
    """
    Test that 'name' field is required in EventDetails.
    Attempting to save an Event without a name should raise a ValidationError.
    """

    details = EventDetails(
        datetime=datetime(2025, 1, 1, 12, 0),
        # 'name' is missing here
    )
    event = Event(details=details)

    with pytest.raises(mongoengine.ValidationError) as excinfo:
        event.save()
    assert "Field is required" in str(excinfo.value)


def test_event_required_datetime(db):
    """
    Test that 'datetime' field is required in EventDetails.
    Attempting to save an Event without a datetime should raise a ValidationError.
    """

    details = EventDetails(
        name="Event Missing Date",
        # 'datetime' is missing
    )
    event = Event(details=details)

    with pytest.raises(mongoengine.ValidationError) as excinfo:
        event.save()
    assert "Field is required" in str(excinfo.value)


def test_add_users_after_creation(db):
    """
    Test updating an existing Event by adding more users.
    """

    details = EventDetails(
        name="Event to Update",
        datetime=datetime(2025, 1, 1, 12, 0),
    )
    event = Event(
        users=[111],
        guild_id=222,
        message_id=333,
        details=details
    )
    event.save()

    # Update and save again
    event.users.append(444)
    event.save()

    retrieved = Event.objects().first()
    assert retrieved.users == [111, 444], "Should contain both users"


def test_set_reactions(db):
    """
    Test setting the reaction counters manually.
    """

    reactions = EventReactions(yes=10, maybe=2, no=1)
    details = EventDetails(
        name="Event With Custom Reactions",
        datetime=datetime(2030, 6, 6, 12, 0),
        reactions=reactions
    )
    Event(details=details).save()

    event = Event.objects().first()
    assert event.details.reactions.yes == 10
    assert event.details.reactions.maybe == 2
    assert event.details.reactions.no == 1

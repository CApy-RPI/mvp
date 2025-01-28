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
    )
    yield
    mongoengine.disconnect()

def test_event_creation(db):
    details = EventDetails(
        name="Test Event",
        datetime=datetime(2025, 1, 1, 12, 0),
    )

    event = Event(
        users=[123, 456],
        guild_id=789,
        message_id=111,
        details=details
    )
    event.save()

    saved_event = Event.objects().first()
    assert saved_event is not None
    assert saved_event.details.name == "Test Event"
    ...

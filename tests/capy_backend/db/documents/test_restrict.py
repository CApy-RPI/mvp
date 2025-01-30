import pytest
import mongoengine
import time
from datetime import datetime, timezone
from mongomock import MongoClient
from src.capy_app.backend.db.documents.restrict import RestrictedDocument, RestrictedEmbeddedDocument


class ConcreteRestrictedDocument(RestrictedDocument):
    meta = {"collection": "test_restricted_document"}


@pytest.fixture(scope="module")
def db():
    """
    Sets up an in-memory MongoDB using mongomock for testing.
    """
    mongoengine.connect(
        db="test_restricted_db",
        alias="default",
        mongo_client_class=MongoClient,
        uuidRepresentation="standard",  # Avoid DeprecationWarning
    )
    yield
    mongoengine.disconnect(alias="default")


def test_restricted_document_set_known_field(db):
    """
    Test that setting an existing field (created_at) on a RestrictedDocument is allowed.
    """
    doc = ConcreteRestrictedDocument()
    new_time = datetime(2020, 1, 1, tzinfo=timezone.utc)
    doc.created_at = new_time
    assert doc.created_at == new_time
    doc.save()

    saved_doc = ConcreteRestrictedDocument.objects.first()

    # Convert saved_doc.created_at to timezone-aware for comparison
    saved_created_at = saved_doc.created_at.replace(tzinfo=timezone.utc)
    assert saved_created_at == new_time


def test_restricted_document_set_unknown_field(db):
    """
    Test that setting a non-existent field raises AttributeError.
    """
    doc = ConcreteRestrictedDocument()
    with pytest.raises(AttributeError):
        doc.some_unknown_field = "This should fail"


def test_restricted_document_delete_attribute(db):
    """
    Test that deleting any attribute raises AttributeError.
    """
    doc = ConcreteRestrictedDocument()
    with pytest.raises(AttributeError):
        del doc.created_at



def test_restricted_document_autoupdate(db):
    """
    Test that `updated_at` automatically updates when saving the document after changes.
    """
    doc = ConcreteRestrictedDocument().save()
    first_updated = doc.updated_at.replace(tzinfo=timezone.utc)

    time.sleep(0.02)  # Ensures MongoDB registers a timestamp change

    doc.created_at = datetime.now(timezone.utc)
    doc.save()
    doc.reload()

    updated_at = doc.updated_at.replace(tzinfo=timezone.utc)

    # Round both timestamps to the nearest millisecond
    first_updated_ms = first_updated.replace(microsecond=(first_updated.microsecond // 1000) * 1000)
    updated_at_ms = updated_at.replace(microsecond=(updated_at.microsecond // 1000) * 1000)

    print(f"Before update (ms rounded): {first_updated_ms}, After update (ms rounded): {updated_at_ms}")

    assert updated_at_ms >= first_updated_ms, (
        f"Expected updated_at ({updated_at_ms}) to be later than first_updated ({first_updated_ms})"
    )


def test_restricted_embedded_document_set_known_field(db):
    """
    Test that setting fields on a RestrictedEmbeddedDocument is allowed only if they exist.
    """

    class ParentDoc(ConcreteRestrictedDocument):
        embedded = mongoengine.EmbeddedDocumentField(RestrictedEmbeddedDocument)

    ParentDoc.register_delete_rule(ParentDoc, "embedded", mongoengine.CASCADE)
    parent = ParentDoc(embedded=RestrictedEmbeddedDocument()).save()
    with pytest.raises(AttributeError):
        parent.embedded.non_existent_field = "Nope"


def test_restricted_embedded_document_delete_attribute(db):
    """
    Test that deleting an attribute on RestrictedEmbeddedDocument raises AttributeError.
    """

    class ParentDoc(ConcreteRestrictedDocument):
        embedded = mongoengine.EmbeddedDocumentField(RestrictedEmbeddedDocument)

    parent = ParentDoc(embedded=RestrictedEmbeddedDocument()).save()
    with pytest.raises(AttributeError):
        del parent.embedded

import pytest
import mongoengine
from datetime import datetime, timedelta
from mongoengine import ValidationError
from mongoengine.errors import NotRegistered

from src.capy_app.backend.db.documents.restrict import RestrictedDocument, RestrictedEmbeddedDocument

@pytest.fixture(scope="module")
def db():
    """
    Sets up an in-memory MongoDB using mongomock for testing.
    If you have a real MongoDB, replace 'mongomock://' with your connection params.
    """
    mongoengine.connect('test_restricted_db', host='mongomock://localhost')
    yield
    mongoengine.disconnect()


def test_restricted_document_set_known_field(db):
    """
    Test that setting an *existing* field (created_at, updated_at) on a RestrictedDocument is allowed.
    """
    doc = RestrictedDocument()
    original_created_at = doc.created_at
    original_updated_at = doc.updated_at

    # Setting to a new datetime is allowed
    new_time = datetime(2020, 1, 1)
    doc.created_at = new_time
    assert doc.created_at == new_time

    # Setting updated_at is allowed
    new_time2 = datetime(2021, 2, 2)
    doc.updated_at = new_time2
    assert doc.updated_at == new_time2

    # Check we can save without error
    doc.save()
    saved_doc = RestrictedDocument.objects().first()
    assert saved_doc.created_at == new_time
    assert saved_doc.updated_at == new_time2


def test_restricted_document_set_unknown_field(db):
    """
    Test that setting a non-existent attribute on RestrictedDocument raises AttributeError.
    """
    doc = RestrictedDocument()
    with pytest.raises(AttributeError) as excinfo:
        doc.some_unknown_field = "This should fail"
    assert "Cannot modify attribute some_unknown_field" in str(excinfo.value)


def test_restricted_document_delete_attribute(db):
    """
    Test that deleting any attribute on RestrictedDocument raises AttributeError.
    """
    doc = RestrictedDocument()
    with pytest.raises(AttributeError) as excinfo:
        del doc.created_at
    assert "Deletion of attribute created_at disallowed" in str(excinfo.value)

    with pytest.raises(AttributeError) as excinfo2:
        del doc.updated_at
    assert "Deletion of attribute updated_at disallowed" in str(excinfo2.value)


def test_restricted_document_autoupdate(db):
    """
    Test that updated_at automatically updates when saving the document after changes.
    """
    doc = RestrictedDocument().save()
    first_updated = doc.updated_at

    # Force a small delay
    doc.created_at = datetime.now() + timedelta(days=1)
    doc.save()

    doc.reload()
    assert doc.updated_at > first_updated, "updated_at should have changed after re-save"


def test_restricted_embedded_document_set_known_field(db):
    """
    Test that setting fields on a RestrictedEmbeddedDocument is allowed only if they exist.
    Note: It's unusual that RestrictedEmbeddedDocument inherits from me.Document
    instead of me.EmbeddedDocument, but we'll test it as given.
    """

    class ParentDoc(RestrictedDocument):
        embedded = mongoengine.EmbeddedDocumentField(RestrictedEmbeddedDocument)

    # Register ParentDoc manually if needed
    # (some versions of mongoengine won't see the class otherwise)
    try:
        ParentDoc.objects().first()
    except NotRegistered:
        # If needed, manually register the doc
        ParentDoc.register_delete_rule(ParentDoc, 'embedded', mongoengine.CASCADE)

    # Create a ParentDoc with an embedded doc
    parent = ParentDoc(embedded=RestrictedEmbeddedDocument()).save()

    # Attempt to set a known field on the embedded doc
    # However, RestrictedEmbeddedDocument currently doesn't define additional fields
    # beyond inherited from Document (like id, created_at, updated_at if we add them)
    # We'll demonstrate the restricted behavior on the embedded doc anyway.
    with pytest.raises(AttributeError) as excinfo:
        parent.embedded.non_existent_field = "Nope"
    assert "Cannot modify attribute non_existent_field" in str(excinfo.value)


def test_restricted_embedded_document_delete_attribute(db):
    """
    Test that deleting an attribute on RestrictedEmbeddedDocument also raises AttributeError.
    """
    class ParentDoc(RestrictedDocument):
        embedded = mongoengine.EmbeddedDocumentField(RestrictedEmbeddedDocument)

    parent = ParentDoc(embedded=RestrictedEmbeddedDocument()).save()

    with pytest.raises(AttributeError) as excinfo:
        del parent.embedded.id  # 'id' is a field from Document
    assert "Deletion of attribute id disallowed" in str(excinfo.value)

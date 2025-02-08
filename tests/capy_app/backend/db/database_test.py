import pytest
import mongoengine
import mongomock

from src.capy_app.backend.db.database import Database
from src.capy_app.backend.db.documents.user import User, UserProfile, UserName


@pytest.fixture(scope="module")
def db():
    mongoengine.disconnect()  # Ensure any existing connections are disconnected
    mongoengine.connect(
        "mongoenginetest",
        host="mongodb://localhost",
        mongo_client_class=mongomock.MongoClient,
        uuidRepresentation="standard",
    )
    db_instance = Database()
    yield db_instance
    mongoengine.disconnect()


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
    assert fetched_user.profile.name.first == "John"  # Enhanced assertion


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


def test_get_nonexistent_user(db):
    """Test retrieving a user that doesn't exist returns None"""
    non_existent_user = db.get_document(User, 999)
    assert non_existent_user is None


def test_update_nonexistent_user(db):
    """Test updating a non-existent user"""
    non_existent_user = User(_id=999, profile=UserProfile(name=UserName(first="Test", last="User")))
    try:
        db.update_document(non_existent_user, {"profile__name__first": "New"})
        pytest.fail("Expected DoesNotExist exception")
    except User.DoesNotExist:
        pass


def test_delete_nonexistent_user(db):
    """Test deleting a non-existent user"""
    non_existent_user = User(_id=999, profile=UserProfile(name=UserName(first="Test", last="User")))
    try:
        db.delete_document(non_existent_user)
        pytest.fail("Expected DoesNotExist exception")
    except User.DoesNotExist:
        pass


def test_add_document_validation_error(db):
    """Test adding an invalid document raises ValidationError"""
    invalid_user = User(_id=1)  # Missing required fields
    with pytest.raises(mongoengine.ValidationError):
        db.add_document(invalid_user)

def test_update_document_invalid_field(db, user):
    """Test updating with invalid field path raises AttributeError"""
    db.add_document(user)
    with pytest.raises(AttributeError):
        db.update_document(user, {"invalid__field__path": "value"})

def test_list_documents_with_filters(db, user, user2):
    """Test listing documents with filters"""
    db.add_document(user)
    db.add_document(user2)
    users = db.list_documents(User, {"profile__major": "Mathematics"})
    assert len(users) == 1
    assert users[0].profile.name.first == "Jane"

def test_sync_document_with_template(db, user):
    """Test synchronizing document with template"""
    # Create a new user with missing fields
    incomplete_user = User(
        _id=3,
        profile=UserProfile(
            name=UserName(first="Test")
        )
    )
    db.add_document(incomplete_user)
    
    # Sync with template
    db.sync_document_with_template(incomplete_user, User)
    
    # Verify fields were synchronized
    synced_user = db.get_document(User, 3)
    assert synced_user.profile.name.last is not None

def test_sync_document_with_invalid_fields(db):
    """Test sync fails with invalid fields"""
    # Create a document with extra fields
    class InvalidUser(User):
        extra_field = mongoengine.StringField()

    invalid_user = InvalidUser(_id=4)
    with pytest.raises(ValueError) as exc_info:
        db.sync_document_with_template(invalid_user, User)
    assert "Fields not in template" in str(exc_info.value)
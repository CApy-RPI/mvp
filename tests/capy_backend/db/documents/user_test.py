import pytest
import mongoengine
import mongomock
from mongoengine.errors import ValidationError, NotUniqueError

from src.capy_app.backend.db.documents.user import User, UserProfile, UserName


@pytest.fixture(scope="module")
def db():
    """
    Create a temporary in-memory test database using mongoengine and mongomock.
    """
    mongoengine.connect(
        db="test_users_db",
        alias="default",  # Set 'default' alias for MongoEngine
        host="mongodb://localhost",
        mongo_client_class=mongomock.MongoClient,  # Use MongoMock explicitly
        uuidRepresentation="standard",
    )
    yield
    mongoengine.disconnect(alias="default")  # Ensure proper cleanup


def test_create_user_success(db):
    """
    Test creating a user with all required fields.
    """
    name = UserName(first="John", last="Doe")
    profile = UserProfile(
        name=name,
        school_email="john.doe@school.edu",
        student_id=12345,
        major=["Computer Science", "Mathematics"],
        graduation_year=2025,
    )

    user = User(
        _id=1,
        guilds=[1001, 1002],
        events=[2001],
        profile=profile,
    )
    user.save()

    # Retrieve from DB
    saved_user = User.objects(_id=1).first()
    assert saved_user is not None, "User should be saved and retrievable."
    assert saved_user.profile.school_email == "john.doe@school.edu"
    assert saved_user.profile.student_id == 12345
    assert saved_user.profile.major == ["Computer Science", "Mathematics"]
    assert saved_user.profile.graduation_year == 2025
    # phone is optional, so it's not set
    assert saved_user.profile.phone is None


def test_missing_required_fields(db):
    """
    Test that creating a user without required fields raises ValidationError.
    We'll omit various required fields in both UserProfile and UserName.
    """
    # Omit 'last' in UserName, 'school_email' and 'major' in UserProfile
    incomplete_name = UserName(first="Jane")
    incomplete_profile = UserProfile(
        name=incomplete_name,
        # missing school_email
        student_id=5555,
        # missing major
        graduation_year=2024,
    )

    user = User(_id=2, profile=incomplete_profile)

    with pytest.raises(ValidationError) as excinfo:
        user.save()
    error_msg = str(excinfo.value)
    assert "Field is required" in error_msg
    assert "last" in error_msg, "Should complain about missing 'last' in UserName"
    assert "school_email" in error_msg, "Should complain about missing 'school_email'"
    assert "major" in error_msg, "Should complain about missing 'major'"


def test_unique_school_email(db):
    """
    Test that creating two users with the same school_email raises NotUniqueError.
    """
    name_a = UserName(first="Alice", last="Smith")
    profile_a = UserProfile(
        name=name_a,
        school_email="unique@school.edu",
        student_id=99999,
        major=["Biology"],
        graduation_year=2023,
    )
    user_a = User(_id=3, profile=profile_a)
    user_a.save()

    name_b = UserName(first="Bob", last="Brown")
    profile_b = UserProfile(
        name=name_b,
        school_email="unique@school.edu",  # Same email
        student_id=88888,
        major=["Chemistry"],
        graduation_year=2023,
    )
    user_b = User(_id=4, profile=profile_b)

    with pytest.raises(NotUniqueError) as excinfo:
        user_b.save()

    # Adjusted assertion to check for duplicate key error
    assert "E11000" in str(
        excinfo.value
    ), "Expected a duplicate key error for school_email"


def test_unique_student_id(db):
    """
    Test that creating two users with the same student_id raises NotUniqueError.
    """
    name_c = UserName(first="Charlie", last="Johnson")
    profile_c = UserProfile(
        name=name_c,
        school_email="charlie@school.edu",
        student_id=77777,
        major=["Physics"],
        graduation_year=2022,
    )
    user_c = User(_id=5, profile=profile_c)
    user_c.save()

    name_d = UserName(first="Diana", last="Green")
    profile_d = UserProfile(
        name=name_d,
        school_email="diana@school.edu",
        student_id=77777,  # Same student ID
        major=["Engineering"],
        graduation_year=2022,
    )
    user_d = User(_id=6, profile=profile_d)

    with pytest.raises(NotUniqueError) as excinfo:
        user_d.save()

    # Adjusted assertion to check for duplicate key error
    assert "E11000" in str(
        excinfo.value
    ), "Expected a duplicate key error for student_id"


def test_optional_phone(db):
    """
    Test that the phone field can be set or left as None without error.
    """
    name = UserName(first="Emily", last="Black")
    profile = UserProfile(
        name=name,
        school_email="emily.black@school.edu",
        student_id=22222,
        major=["Art History"],
        graduation_year=2026,
        phone=1234567890,
    )
    user = User(_id=7, profile=profile).save()

    saved_user = User.objects(_id=7).first()
    assert saved_user.profile.phone == 1234567890

    # Update phone to None
    saved_user.profile.phone = None
    saved_user.save()

    updated_user = User.objects(_id=7).first()
    assert updated_user.profile.phone is None


def test_add_guilds_and_events(db):
    """
    Test adding guild and event references to an existing user.
    """
    name = UserName(first="Frank", last="Wright")
    profile = UserProfile(
        name=name,
        school_email="frank.wright@school.edu",
        student_id=33333,
        major=["Economics"],
        graduation_year=2025,
    )
    user = User(_id=8, profile=profile).save()

    # Add some guilds and events
    user.guilds = [5001, 5002]
    user.events = [6001]
    user.save()

    saved_user = User.objects(_id=8).first()
    assert saved_user.guilds == [5001, 5002]
    assert saved_user.events == [6001]

    # Append more
    saved_user.guilds.append(5003)
    saved_user.events.append(6002)
    saved_user.save()

    updated_user = User.objects(_id=8).first()
    assert updated_user.guilds == [5001, 5002, 5003]
    assert updated_user.events == [6001, 6002]

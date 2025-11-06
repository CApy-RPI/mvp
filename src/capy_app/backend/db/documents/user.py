import datetime
import typing

import mongoengine
from backend.db.documents.restrict import (
    RestrictedDocument,
    RestrictedEmbeddedDocument,
)


class OfficeHours(mongoengine.EmbeddedDocument):
    """Represents a user's weekly office hours schedule."""

    monday = mongoengine.ListField(mongoengine.StringField(), default=list)
    tuesday = mongoengine.ListField(mongoengine.StringField(), default=list)
    wednesday = mongoengine.ListField(mongoengine.StringField(), default=list)
    thursday = mongoengine.ListField(mongoengine.StringField(), default=list)
    friday = mongoengine.ListField(mongoengine.StringField(), default=list)
    saturday = mongoengine.ListField(mongoengine.StringField(), default=list)
    sunday = mongoengine.ListField(mongoengine.StringField(), default=list)


class UserName(RestrictedEmbeddedDocument):
    """Represents a user's name with first, middle, and last components.

    Attributes:
        first: User's first name
        middle: User's middle name (optional)
        last: User's last name
    """

    first: str = mongoengine.StringField(required=True)
    middle: str = mongoengine.StringField()
    last: str = mongoengine.StringField(required=True)


class UserProfile(RestrictedEmbeddedDocument):
    """Represents detailed user profile information.

    Attributes:
        name: User's full name components
        school_email: User's academic email address
        student_id: Unique student identification number
        major: User's declared majors as a string
        graduation_year: Expected graduation year
        phone: Contact phone number (optional)
    """

    name: UserName = mongoengine.EmbeddedDocumentField(UserName, required=True)
    school_email: str = mongoengine.EmailField(required=True, unique=True)
    student_id: int = mongoengine.IntField(required=True, unique=True)
    major: str = mongoengine.StringField(required=True)
    graduation_year: int = mongoengine.IntField(required=True)
    phone: int = mongoengine.IntField()


class User(RestrictedDocument):
    """Main user document storing core user data and relationships.

    Attributes:
        _id: Unique identifier for the user
        guilds: List of guild IDs the user belongs to
        events: List of event IDs the user is participating in
        profile: Detailed user profile information
        created_at: Timestamp when the user was created
        updated_at: Timestamp of last update
    """

    _id: int = mongoengine.LongField(primary_key=True)
    guilds: list[int] = mongoengine.ListField(mongoengine.LongField())
    events: list[int] = mongoengine.ListField(mongoengine.LongField())
    profile: UserProfile = mongoengine.EmbeddedDocumentField(UserProfile, required=True)
    created_at: datetime.datetime = mongoengine.DateTimeField(default=datetime.datetime.now)
    updated_at: datetime.datetime = mongoengine.DateTimeField(default=datetime.datetime.now)
    office_hours: OfficeHours = mongoengine.EmbeddedDocumentField(OfficeHours, default=OfficeHours)

    meta: typing.ClassVar[dict[str, typing.Any]] = {
        "collection": "users",
        "indexes": ["created_at", "updated_at"],
    }

    def save(self, *args: typing.Any, **kwargs: typing.Any) -> "User":
        """Override save to update the updated_at timestamp."""
        self.updated_at = datetime.datetime.now()
        result = super().save(*args, **kwargs)
        return typing.cast("User", result)

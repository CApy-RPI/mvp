import typing
import datetime
import mongoengine


class UserName(mongoengine.EmbeddedDocument):
    """Represents a user's name with first, middle, and last components.

    Attributes:
        first: User's first name
        middle: User's middle name (optional)
        last: User's last name
    """

    first: str = mongoengine.StringField(required=True)
    middle: str = mongoengine.StringField()
    last: str = mongoengine.StringField(required=True)


class UserProfile(mongoengine.EmbeddedDocument):
    """Represents detailed user profile information.

    Attributes:
        name: User's full name components
        school_email: User's academic email address
        student_id: Unique student identification number
        major: List of user's declared majors
        graduation_year: Expected graduation year
        phone: Contact phone number (optional)
    """

    name: UserName = mongoengine.EmbeddedDocumentField(UserName, required=True)
    school_email: str = mongoengine.EmailField(required=True, unique=True)
    student_id: int = mongoengine.IntField(required=True, unique=True)
    major: typing.List[str] = mongoengine.ListField(
        mongoengine.StringField(), required=True
    )
    graduation_year: int = mongoengine.IntField(required=True)
    phone: int = mongoengine.IntField()


class User(mongoengine.Document):
    """Main user document storing core user data and relationships.

    Attributes:
        _id: Unique identifier for the user
        guilds: List of guild IDs the user belongs to
        events: List of event IDs the user is participating in
        profile: Detailed user profile information
        created_at: Timestamp when the user was created
        updated_at: Timestamp of last update
    """

    _id: int = mongoengine.IntField(primary_key=True)
    guilds: typing.List[int] = mongoengine.ListField(mongoengine.IntField())
    events: typing.List[int] = mongoengine.ListField(mongoengine.IntField())
    profile: UserProfile = mongoengine.EmbeddedDocumentField(UserProfile, required=True)
    created_at: datetime.datetime = mongoengine.DateTimeField(
        default=datetime.datetime.utcnow
    )
    updated_at: datetime.datetime = mongoengine.DateTimeField(
        default=datetime.datetime.utcnow
    )

    meta = {"collection": "users", "indexes": ["created_at", "updated_at"]}

    def save(self, *args: typing.Any, **kwargs: typing.Any) -> "User":
        """Override save to update the updated_at timestamp."""
        self.updated_at = datetime.datetime.utcnow()
        result = super().save(*args, **kwargs)
        return typing.cast("User", result)

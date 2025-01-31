import mongoengine as me


class UserName(me.EmbeddedDocument):
    """
    A class to represent a user's name.

    Attributes:
        first (str): The first name of the user.
        middle (str): The middle name of the user.
        last (str): The last name of the user.
    """

    first = me.StringField(required=True)
    middle = me.StringField()
    last = me.StringField(required=True)


class UserProfile(me.EmbeddedDocument):
    """
    A class to represent a user's profile.

    Attributes:
        name (UserName): The name of the user.
        school_email (str): The school email of the user.
        student_id (int): The student ID of the user.
        major (List[str]): The major(s) of the user.
        graduation_year (int): The graduation year of the user.
        phone (int): The phone number of the user.
    """

    name = me.EmbeddedDocumentField(UserName, required=True)
    school_email = me.EmailField(required=True, unique=True)
    student_id = me.IntField(required=True, unique=True)
    major = me.ListField(me.StringField(), required=True)
    graduation_year = me.IntField(required=True)
    phone = me.IntField()


class User(me.Document):
    """
    A class to represent a user.

    Attributes:
        _id (int): The primary key of the user.
        guilds (List[int]): The list of guild IDs the user is part of.
        events (List[int]): The list of event IDs the user is part of.
        profile (UserProfile): The profile of the user.
    """

    _id = me.IntField(primary_key=True)
    guilds = me.ListField(me.IntField())
    events = me.ListField(me.IntField())
    profile = me.EmbeddedDocumentField(UserProfile, required=True)

    meta = {"collection": "users"}

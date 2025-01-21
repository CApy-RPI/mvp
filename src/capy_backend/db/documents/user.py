import mongoengine as me

from .restricted import RestrictedDocument, RestrictedEmbeddedDocument


class UserName(RestrictedEmbeddedDocument):
    first = me.StringField(required=True)
    middle = me.StringField
    last = me.StringField(required=True)


class UserProfile(RestrictedEmbeddedDocument):
    name = me.EmbeddedDocumentField(UserName, required=True)
    school_email = me.EmailField(required=True, unique=True)
    student_id = me.IntField(required=True, unique=True)
    major = me.ListField(me.StringField(), required=True)
    graduation_year = me.IntField(required=True)
    phone = me.IntField()


class User(RestrictedDocument):
    _id = me.IntField(primary_key=True)
    guilds = me.ListField(me.IntField())
    events = me.ListField(me.IntField())
    profile = me.EmbeddedDocumentField(UserProfile, required=True)

    meta = {**RestrictedDocument.meta, "collection": "users"}

import mongoengine as me
from datetime import datetime


class RestrictedBase:
    meta = {"allow_inheritance": True}

    def __setattr__(self, name, value):
        if name not in self._fields:
            raise AttributeError(
                f"Cannot modify attribute {name} on {self.__class__.__name__} as it does not exist."
            )
        super().__setattr__(name, value)

    def __delattr__(self, name):
        raise AttributeError(
            f"Deletion of attribute {name} disallowed on {self.__class__.__name__}"
        )


class RestrictedDocument(RestrictedBase, me.Document):
    created_at = me.DateTimeField(default=datetime.utcnow)
    updated_at = me.DateTimeField(default=datetime.utcnow, auto_now=True)


class RestrictedEmbeddedDocument(RestrictedBase, me.Document):
    pass

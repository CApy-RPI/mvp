import mongoengine as me
from datetime import datetime, timezone


class RestrictedBase:
    meta = {"allow_inheritance": True}

    def __setattr__(self, name, value):
        if not name.startswith("_") and name not in self._fields:
            raise AttributeError(
                f"Cannot modify attribute {name} on {self.__class__.__name__} as it does not exist."
            )
        super().__setattr__(name, value)

    def __delattr__(self, name):
        raise AttributeError(
            f"Deletion of attribute {name} disallowed on {self.__class__.__name__}"
        )


class RestrictedDocument(RestrictedBase, me.Document):
    created_at = me.DateTimeField(default=lambda: datetime.now(timezone.utc))
    updated_at = me.DateTimeField(default=lambda: datetime.now(timezone.utc), auto_now=True)

    meta = {"abstract": True}


class RestrictedEmbeddedDocument(RestrictedBase, me.EmbeddedDocument):
    pass

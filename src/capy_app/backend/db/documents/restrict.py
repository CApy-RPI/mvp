import typing
import datetime
import mongoengine


class RestrictedBase(mongoengine.Document):
    """Base class for restricted documents with proper type hints."""

    _fields: typing.ClassVar[typing.Dict[str, mongoengine.BaseField]]
    meta = {"abstract": True}

    @classmethod
    def get_fields(cls) -> typing.Dict[str, mongoengine.BaseField]:
        """Get document fields with proper type hints."""
        return cls._fields

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


class RestrictedDocument(RestrictedBase, mongoengine.Document):
    created_at = mongoengine.DateTimeField(
        default=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    updated_at = mongoengine.DateTimeField(
        default=lambda: datetime.datetime.now(datetime.timezone.utc), auto_now=True
    )

    meta = {"abstract": True}


class RestrictedEmbeddedDocument(RestrictedBase, mongoengine.EmbeddedDocument):
    pass

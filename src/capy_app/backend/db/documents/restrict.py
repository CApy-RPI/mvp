import datetime

import logging
from typing import Any, Dict

import mongoengine
from mongoengine.base import BaseDocument


class RestrictedBase(BaseDocument):
    """Base class for restricted documents with proper type hints."""

    meta: Dict[str, Any] = {"abstract": True}
    logger = logging.getLogger(__name__)

    def __setattr__(self, name, value):
        if not name.startswith("_") and name not in self._fields:
            err = AttributeError(
                f"Cannot modify attribute {name} on {self.__class__.__name__} as it does not exist."
            )

            self.logger.exception(err, stack_info=True)
            raise err
        super().__setattr__(name, value)

    def __delattr__(self, name):
        err = AttributeError(
            f"Deletion of attribute {name} disallowed on {self.__class__.__name__}"
        )
        self.logger.exception(err, stack_info=True)
        raise err


class RestrictedDocument(RestrictedBase, mongoengine.Document):
    created_at = mongoengine.DateTimeField(
        default=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    updated_at = mongoengine.DateTimeField(
        default=lambda: datetime.datetime.now(datetime.timezone.utc), auto_now=True
    )

    meta: Dict[str, Any] = {"abstract": True}


class RestrictedEmbeddedDocument(RestrictedBase, mongoengine.EmbeddedDocument):
    meta: Dict[str, Any] = {"allow_inheritance": True}

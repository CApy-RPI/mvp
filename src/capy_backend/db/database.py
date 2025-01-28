import mongoengine as me
from datetime import datetime
from typing import Type, TypeVar, Optional, Dict, Any, List

from src.config import MONGO_URI, MONGO_DBNAME, MONGO_PASSWORD, MONGO_USERNAME

T = TypeVar("T", bound=me.Document)

me.connect(
    db=MONGO_DBNAME, username=MONGO_USERNAME, password=MONGO_PASSWORD, host=MONGO_URI
)


class Database:
    @staticmethod
    def add_document(document: T) -> T:
        document.save()
        return document

    @staticmethod
    def get_document(document_class: Type[T], document_id: Any) -> Optional[T]:
        return document_class.objects(pk=document_id).first()

    @staticmethod
    def update_document(document: T, updates: Dict[str, Any]) -> T:
        for key, value in updates.items():
            keys = key.split("__")
            target = document
            for k in keys[:-1]:
                target = getattr(target, k)
            setattr(target, keys[-1], value)
        document.save()
        return document

    @staticmethod
    def delete_document(document: T) -> None:
        document.delete()

    @staticmethod
    def list_documents(
        document_class: Type[T], filters: Dict[str, Any] = None
    ) -> List[T]:
        if filters is None:
            filters = {}
        return document_class.objects(**filters)

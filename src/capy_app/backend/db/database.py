import mongoengine as me
from typing import Type, TypeVar, Optional, Dict, Any, List

from config import MONGO_URI, MONGO_DBNAME, MONGO_PASSWORD, MONGO_USERNAME

T = TypeVar("T", bound=me.Document)

me.connect(
    db=MONGO_DBNAME,
    username=MONGO_USERNAME,
    password=MONGO_PASSWORD,
    host=MONGO_URI,
    uuidRepresentation="standard",
)


class Database:
    """
    A class to handle basic database operations using MongoEngine.
    """

    @staticmethod
    def add_document(document: T) -> T:
        """
        Add a new document to the database.

        Args:
            document (T): The document to be added.

        Returns:
            T: The saved document.
        """
        document.save()
        return document

    @staticmethod
    def get_document(document_class: Type[T], document_id: Any) -> Optional[T]:
        """
        Retrieve a document from the database by its ID.

        Args:
            document_class (Type[T]): The class of the document.
            document_id (Any): The ID of the document.

        Returns:
            Optional[T]: The retrieved document or None if not found.
        """
        return document_class.objects(pk=document_id).first()

    @staticmethod
    def update_document(document: T, updates: Dict[str, Any]) -> T:
        """
        Update an existing document with the provided updates.

        Args:
            document (T): The document to be updated.
            updates (Dict[str, Any]): A dictionary of updates to apply.

        Returns:
            T: The updated document.
        """
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
        """
        Delete a document from the database.

        Args:
            document (T): The document to be deleted.
        """
        document.delete()

    @staticmethod
    def list_documents(
        document_class: Type[T], filters: Dict[str, Any] = None
    ) -> List[T]:
        """
        List documents from the database based on the provided filters.

        Args:
            document_class (Type[T]): The class of the documents.
            filters (Dict[str, Any], optional): A dictionary of filters to apply. Defaults to None.

        Returns:
            List[T]: A list of documents that match the filters.
        """
        if filters is None:
            filters = {}
        return document_class.objects(**filters)

    @staticmethod
    def sync_document_with_template(document: T, template: Type[T]) -> None:
        """
        Ensure a document has the same values as the current template.

        Args:
            document (T): The document to be synced.
            template (Type[T]): The template class to sync with.
        """

        def sync_fields(doc, tmpl):
            for field in tmpl._fields:
                if not hasattr(doc, field):
                    setattr(doc, field, getattr(tmpl, field))
                else:
                    value = getattr(doc, field)
                    if isinstance(value, me.EmbeddedDocument):
                        sync_fields(value, getattr(tmpl, field))
                    else:
                        setattr(tmpl, field, value)

            for field in doc._fields:
                if field not in tmpl._fields:
                    raise ValueError(
                        f"Warning: Field '{field}' in document is not in the template and will be ignored."
                    )

        template_instance = template()
        sync_fields(document, template_instance)
        document.save()

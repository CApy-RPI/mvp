import typing

import mongoengine

from config import settings

T = typing.TypeVar("T", bound=mongoengine.Document)

mongoengine.connect(
    db=settings.MONGO_DBNAME,
    username=settings.MONGO_USERNAME,
    password=settings.MONGO_PASSWORD,
    host=settings.MONGO_URI,
    uuidRepresentation="standard",
)


class Database:
    """Provides high-level database operations using MongoEngine."""

    @staticmethod
    def add_document(document: T) -> T:
        """Creates a new document in the database.

        Args:
            document: Document instance to be saved

        Returns:
            The saved document with updated metadata

        Raises:
            ValidationError: If document validation fails
            OperationError: If database operation fails
        """
        document.save()
        return document

    @staticmethod
    def get_document(document_class: type[T], document_id: typing.Any) -> T | None:
        """Retrieves a document by its ID.

        Args:
            document_class: Class of the document to retrieve
            document_id: Primary key value of the document

        Returns:
            Retrieved document or None if not found
        """
        result = document_class.objects(pk=document_id).first()
        return typing.cast(T | None, result)

    @staticmethod
    def update_document(document: T, updates: dict[str, typing.Any]) -> T:
        """Updates an existing document with provided changes.

        Args:
            document: Document instance to update
            updates: Dictionary of field paths and their new values

        Returns:
            Updated document instance

        Raises:
            AttributeError: If field path is invalid
            ValidationError: If new values are invalid
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
        """Removes a document from the database.

        Args:
            document: Document instance to delete

        Raises:
            OperationError: If deletion fails
        """
        document.delete()

    @staticmethod
    def delete_document_by_id(document: T, document_id: int) -> None:
        """Removes a document from the database.

        Args:
            document: Document instance to delete

        Raises:
            OperationError: If deletion fails
        """
        document.objects(pk=document_id).delete()

    @staticmethod
    def list_documents(
        document_class: type[T],
        filters: dict[str, typing.Any] | None = None,
    ) -> list[T]:
        """Retrieves documents matching specified filters.

        Args:
            document_class: Class of documents to query
            filters: Query filters to apply

        Returns:
            List of matching documents
        """
        return list(document_class.objects(**(filters or {})))

    @staticmethod
    def list_document_attr(
        document_class: type[T],
        attribute: str,
        filters: dict[str, typing.Any] | None = None,
    ) -> list[typing.Any]:
        """Retrieve values for a single attribute across matching documents.

        This minimizes payload by projecting only the requested attribute.

        Args:
            document_class: Class of documents to query
            attribute: Field name to return (e.g., "id", "guilds")
            filters: Optional query filters

        Returns:
            List of attribute values, ordered by query result order
        """
        qs = document_class.objects(**(filters or {})).only(attribute)

        # Special-case primary key for reliability and typing consistency
        if attribute in {"id", "pk", "_id"}:
            return [int(doc.pk) for doc in qs]

        return [getattr(doc, attribute) for doc in qs]

    @staticmethod
    def bulk_update_attr(
        document_class: type[T],
        ids: list[int],
        attribute: str,
        value: typing.Any,
    ) -> int:
        """Bulk update an attribute for all documents with given IDs.

        If the attribute is a ListField, appends the value; otherwise sets it.

        Args:
            document_class: MongoEngine Document subclass to update
            ids: List of primary key IDs to target
            attribute: Top-level field name to update
            value: Value to set or append

        Returns:
            Number of documents updated
        """
        if not ids:
            return 0

        # Determine field type (top-level only)
        field = document_class._fields.get(attribute)  # type: ignore[attr-defined]
        qs = document_class.objects(pk__in=ids)

        # If it's a ListField, append uniquely (server-side), otherwise set the value.
        try:
            if isinstance(field, mongoengine.fields.ListField):  # type: ignore[attr-defined]
                # Use add_to_set to avoid duplicates without fetching documents
                updated = qs.update(**{f"add_to_set__{attribute}": value})
            else:
                updated = qs.update(**{f"set__{attribute}": value})
        except Exception:
            # Fallback to set if field introspection fails
            updated = qs.update(**{f"set__{attribute}": value})

        return int(updated)

    # @staticmethod
    # def sync_document_with_template(document: T, template: typing.Type[T]) -> None:
    #     """Synchronizes document fields with template structure.
    #     Args:
    #         document: Document instance to sync
    #         template: Template class to sync against
    #     Raises:
    #         ValueError: If document has fields not in template
    #     """

    #     def sync_fields(doc: typing.Any, tmpl: typing.Any) -> None:
    #         """Recursively syncs fields between document and template."""
    #         for field in tmpl._fields:
    #             if not hasattr(doc, field):
    #                 setattr(doc, field, getattr(tmpl, field))
    #             else:
    #                 value = getattr(doc, field)
    #                 if isinstance(value, mongoengine.EmbeddedDocument):
    #                     sync_fields(value, getattr(tmpl, field))
    #                 else:
    #                     setattr(tmpl, field, value)

    #         extra_fields = set(doc._fields) - set(tmpl._fields)
    #         if extra_fields:
    #             raise ValueError(f"Fields not in template: {', '.join(extra_fields)}")

    #     template_instance = template()
    #     sync_fields(document, template_instance)
    #     document.save()

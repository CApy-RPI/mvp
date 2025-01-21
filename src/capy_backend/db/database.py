import mongoengine as me
from typing import Type, TypeVar, Optional, Dict, Any, List

from config import MONGO_URI

# -------------------- Dynamic MongoDB Connection --------------------
if not me.connection_initialized():
    me.connect(host=MONGO_URI)

# Define a generic type for MongoEngine Documents
T = TypeVar("T", bound=me.Document)


class Database:
    """A dynamic MongoEngine database handler."""

    @staticmethod
    def insert(document: T) -> str:
        """Insert a document and return its ID."""
        document.save()
        return str(document.id)

    @staticmethod
    def bulk_insert(documents: List[T]) -> List[str]:
        """Insert multiple documents at once and return their IDs."""
        if documents:
            me.Document.save(documents)
            return [str(doc.id) for doc in documents]
        return []

    @staticmethod
    def get(document_class: Type[T], document_id: str) -> Optional[T]:
        """Retrieve a document by ID. Returns the document itself for modification."""
        return document_class.objects(id=document_id).first()

    @staticmethod
    def get_all(document_class: Type[T], filters: Dict[str, Any] = None) -> List[T]:
        """Retrieve all documents matching the filter and return them."""
        filters = filters or {}
        return list(document_class.objects(**filters))

    @staticmethod
    def update(document: T) -> bool:
        """Update an existing document by calling `.save()` on it."""
        if document:
            document.save()
            return True
        return False

    @staticmethod
    def delete(document: T) -> bool:
        """Delete an existing document by calling `.delete()` on it."""
        if document:
            document.delete()
            return True
        return False

    @staticmethod
    def upsert(
        document_class: Type[T], filters: Dict[str, Any], update_data: Dict[str, Any]
    ) -> T:
        """
        Upsert (insert or update) a document based on filters.
        Returns the document itself so it can be modified.
        """
        document = document_class.objects(**filters).modify(
            upsert=True, new=True, set__=update_data
        )
        return document


# -------------------- Example Usage --------------------
if __name__ == "__main__":
    from documents.guild import Guild

    db = Database()

    # Insert or update a Guild
    guild = db.upsert(
        Guild,
        filters={"id": "guild_001"},
        update_data={
            "users": ["user1", "user2"],
            "channels": {"reports": "report-channel"},
        },
    )
    print(f"Upserted Guild: {guild.to_json()}")

    # Modify the document and update
    guild.users.append("user3")
    db.update(guild)

    # Retrieve and modify again
    retrieved_guild = db.get(Guild, "guild_001")
    if retrieved_guild:
        retrieved_guild.channels.announcements = "announcements-channel"
        db.update(retrieved_guild)

    print("Updated Guild:", retrieved_guild.to_json())

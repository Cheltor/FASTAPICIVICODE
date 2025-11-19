from sqlalchemy.orm import Session
from sqlalchemy import or_
from CiviCodeAPI import models

def search_codes(db: Session, query: str):
    """
    Searches for codes by a query string in their name or description.

    Args:
        db: The database session.
        query: The string to search for.

    Returns:
        A list of Code objects matching the query.
    """
    if not query:
        return []

    search_query = f"%{query}%"
    return db.query(models.Code).filter(
        or_(
            models.Code.name.ilike(search_query),
            models.Code.description.ilike(search_query)
        )
    ).all()

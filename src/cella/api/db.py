"""Database session wiring (SQLAlchemy 2.0 over PostgreSQL).

TODO(P1): define ORM models mirroring docs/CONCEPT.md §6
(ORGAN, CELL_TYPE, CELL_TYPE_ORGAN, GENE, WEIGHT, GRAPH_EDGE) and Alembic
migrations. This module only holds the engine/session factory for now.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from cella.core.config import settings

engine = create_engine(settings.database_url, future=True)
SessionLocal = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """FastAPI dependency yielding a scoped DB session."""
    with SessionLocal() as session:
        yield session

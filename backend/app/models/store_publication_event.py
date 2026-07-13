import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class StorePublicationEvent(Base):
    __tablename__ = "store_publication_events"

    __table_args__ = (
        CheckConstraint(
            "action IN ('publish', 'unpublish')",
            name=(
                "ck_store_publication_events_action"
            ),
        ),
        CheckConstraint(
            (
                "previous_publication_status "
                "IN ('draft', 'published')"
            ),
            name=(
                "ck_store_publication_events_"
                "previous_status"
            ),
        ),
        CheckConstraint(
            (
                "new_publication_status "
                "IN ('draft', 'published')"
            ),
            name=(
                "ck_store_publication_events_"
                "new_status"
            ),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "stores.id",
            name=(
                "fk_store_publication_events_"
                "store_id_stores"
            ),
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    actor_user_id: Mapped[
        uuid.UUID | None
    ] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            name=(
                "fk_store_publication_events_"
                "actor_user_id_users"
            ),
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    actor_role: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    action: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    previous_publication_status: Mapped[str] = (
        mapped_column(
            String(20),
            nullable=False,
        )
    )

    new_publication_status: Mapped[str] = (
        mapped_column(
            String(20),
            nullable=False,
        )
    )

    reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    readiness_snapshot: Mapped[
        dict[str, Any]
    ] = mapped_column(
        JSONB,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


Index(
    (
        "ix_store_publication_events_"
        "store_created_at_id_desc"
    ),
    StorePublicationEvent.store_id,
    StorePublicationEvent.created_at.desc(),
    StorePublicationEvent.id.desc(),
)

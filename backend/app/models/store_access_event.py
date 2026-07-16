import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class StoreAccessEvent(Base):
    __tablename__ = "store_access_events"

    __table_args__ = (
        CheckConstraint(
            (
                "action IN ("
                "'activate', "
                "'deactivate', "
                "'suspend', "
                "'unsuspend'"
                ")"
            ),
            name=(
                "ck_store_access_events_action"
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
                "fk_store_access_events_"
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
                "fk_store_access_events_"
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
        String(30),
        nullable=False,
    )

    previous_is_active: Mapped[bool] = (
        mapped_column(
            Boolean,
            nullable=False,
        )
    )

    new_is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )

    previous_is_suspended: Mapped[bool] = (
        mapped_column(
            Boolean,
            nullable=False,
        )
    )

    new_is_suspended: Mapped[bool] = (
        mapped_column(
            Boolean,
            nullable=False,
        )
    )

    previous_subscription_status: Mapped[
        str
    ] = mapped_column(
        String(30),
        nullable=False,
    )

    new_subscription_status: Mapped[
        str
    ] = mapped_column(
        String(30),
        nullable=False,
    )

    reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


Index(
    (
        "ix_store_access_events_"
        "store_created_at_id_desc"
    ),
    StoreAccessEvent.store_id,
    StoreAccessEvent.created_at.desc(),
    StoreAccessEvent.id.desc(),
)
import uuid
from datetime import datetime

from sqlalchemy import (
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


class SellerAccountEvent(Base):
    __tablename__ = "seller_account_events"

    __table_args__ = (
        CheckConstraint(
            "action IN ('suspend', 'reactivate')",
            name=(
                "ck_seller_account_events_action"
            ),
        ),
        CheckConstraint(
            (
                "previous_account_status "
                "IN ('active', 'suspended')"
            ),
            name=(
                "ck_seller_account_events_"
                "previous_status"
            ),
        ),
        CheckConstraint(
            (
                "new_account_status "
                "IN ('active', 'suspended')"
            ),
            name=(
                "ck_seller_account_events_"
                "new_status"
            ),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    seller_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            name=(
                "fk_seller_account_events_"
                "seller_id_users"
            ),
            ondelete="CASCADE",
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
                "fk_seller_account_events_"
                "actor_user_id_users"
            ),
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    action: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    previous_account_status: Mapped[str] = (
        mapped_column(
            String(20),
            nullable=False,
        )
    )

    new_account_status: Mapped[str] = (
        mapped_column(
            String(20),
            nullable=False,
        )
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
        "ix_seller_account_events_"
        "seller_created_at_id_desc"
    ),
    SellerAccountEvent.seller_id,
    SellerAccountEvent.created_at.desc(),
    SellerAccountEvent.id.desc(),
)

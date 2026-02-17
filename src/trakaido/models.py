"""Trakaido-specific SQLAlchemy models."""

from datetime import datetime, timedelta
import enum
import secrets
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.models import Base


class ClassroomRole(enum.Enum):
    """Roles for classroom membership."""

    MANAGER = "manager"
    MEMBER = "member"


class Classroom(Base):
    """A Trakaido classroom."""

    __tablename__ = "classrooms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_by_user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    memberships = relationship(
        "ClassroomMembership", back_populates="classroom", cascade="all, delete-orphan"
    )


class ClassroomMembership(Base):
    """User membership in a classroom."""

    __tablename__ = "classroom_memberships"
    __table_args__ = (
        UniqueConstraint(
            "classroom_id",
            "user_id",
            name="uq_classroom_memberships_classroom_id_user_id",
        ),
        Index("ix_classroom_memberships_classroom_id_role", "classroom_id", "role"),
        Index("ix_classroom_memberships_user_id_role", "user_id", "role"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    classroom_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("classrooms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[ClassroomRole] = mapped_column(
        Enum(
            ClassroomRole,
            values_callable=lambda enum_cls: [role.value for role in enum_cls],
            name="classroom_role",
        ),
        nullable=False,
        default=ClassroomRole.MEMBER,
    )
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    classroom = relationship("Classroom", back_populates="memberships")


class ClassroomInviteToken(Base):
    """Optional invite link token for classroom onboarding."""

    __tablename__ = "classroom_invite_tokens"
    __table_args__ = (
        Index("ix_classroom_invite_tokens_classroom_id_active", "classroom_id", "is_active"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    classroom_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("classrooms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    created_by_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    max_uses: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    current_uses: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    classroom = relationship("Classroom")

    @classmethod
    def generate_token(cls, token_length: int = 32) -> str:
        """Generate a URL-safe invite token."""
        return secrets.token_urlsafe(token_length)

    @classmethod
    def default_expiry(cls, days: int = 14) -> datetime:
        """Generate a default expiration datetime."""
        return datetime.utcnow() + timedelta(days=days)

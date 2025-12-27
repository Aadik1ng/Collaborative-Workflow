"""User SQLAlchemy model."""

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.postgres import Base

if TYPE_CHECKING:
    from app.models.sql.project import Project
    from app.models.sql.role import ProjectCollaborator


class User(Base):
    """User model for authentication and identification."""

    __tablename__ = "cw_users"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    username: Mapped[str] = mapped_column(
        String(100), unique=True, index=True, nullable=False
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    owned_projects: Mapped[List["Project"]] = relationship(
        "Project", back_populates="owner", cascade="all, delete-orphan"
    )
    collaborations: Mapped[List["ProjectCollaborator"]] = relationship(
        "ProjectCollaborator",
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="[ProjectCollaborator.user_id]",
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email})>"

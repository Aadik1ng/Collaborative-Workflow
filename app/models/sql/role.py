"""ProjectCollaborator SQLAlchemy model for role-based access."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.permissions import Role
from app.db.postgres import Base

if TYPE_CHECKING:
    from app.models.sql.project import Project
    from app.models.sql.user import User


class ProjectCollaborator(Base):
    """Model for managing project collaborators and their roles."""

    __tablename__ = "project_collaborators"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    role: Mapped[str] = mapped_column(
        String(50), default=Role.VIEWER.value, nullable=False
    )
    invited_by: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    invited_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    accepted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Unique constraint: one role per user per project
    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_project_collaborator"),
    )

    # Relationships
    project: Mapped["Project"] = relationship(
        "Project", back_populates="collaborators"
    )
    user: Mapped["User"] = relationship(
        "User", back_populates="collaborations", foreign_keys=[user_id]
    )

    def __repr__(self) -> str:
        return f"<ProjectCollaborator(project_id={self.project_id}, user_id={self.user_id}, role={self.role})>"

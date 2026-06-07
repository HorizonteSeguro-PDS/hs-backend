import uuid
from datetime import datetime

from sqlalchemy import Enum as PgEnum, Index, func
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from domain.audit.enums import AuditAction, AuditEntityType
from utils.database import Base

# Migration 0003 turned `audit_log.action` and `audit_log.entity_type` into
# Postgres native enums. The model has to match the DB types — otherwise
# SQLAlchemy sends VARCHAR params on INSERT and Postgres rejects with
# ProgrammingError (column type mismatch).

audit_action_pg = PgEnum(
    AuditAction,
    name="audit_action",
    create_type=False,
    values_callable=lambda obj: [e.value for e in obj],
)
audit_entity_type_pg = PgEnum(
    AuditEntityType,
    name="audit_entity_type",
    create_type=False,
    values_callable=lambda obj: [e.value for e in obj],
)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    entity_type: Mapped[AuditEntityType] = mapped_column(
        audit_entity_type_pg, nullable=False
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    action: Mapped[AuditAction] = mapped_column(audit_action_pg, nullable=False)
    # TODO: add FK to users(id) once users table exists
    author_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_audit_entity", "entity_type", "entity_id"),
        Index("ix_audit_author", "author_id"),
        # ix_audit_created is created as DESC in the migration via raw DDL
    )

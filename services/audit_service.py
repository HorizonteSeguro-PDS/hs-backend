from uuid import UUID

from sqlalchemy.orm import Session

from domain.models.audit_log import AuditLog


def audit_event(
    session: Session,
    *,
    entity_type: str,
    entity_id: UUID,
    action: str,
    author_id: UUID,
    payload: dict | None = None,
) -> AuditLog:
    """
    Persist an audit event within the current transaction.

    Does NOT commit — the caller is responsible for committing so that the
    audit record and the audited operation land in the same transaction.
    """
    log = AuditLog(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        author_id=author_id,
        payload=payload,
    )
    session.add(log)
    session.flush()
    return log

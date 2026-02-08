"""
Audit log service. All audit log creation goes through here.
"""

import logging

from .models import AuditAction, AuditLog

logger = logging.getLogger(__name__)


def log_audit(
    *,
    action: str,
    user=None,
    ip_address: str | None = None,
    company=None,
    target_model: str = "",
    target_id: str = "",
    details: dict | None = None,
) -> AuditLog:
    """
    Create an audit log entry. This is the ONLY way to create audit entries.
    All parameters are keyword-only to prevent positional argument mistakes.
    """
    entry = AuditLog.objects.create(
        action=action,
        user=user,
        ip_address=ip_address,
        company=company,
        target_model=target_model,
        target_id=str(target_id) if target_id else "",
        details=details or {},
    )
    logger.info(
        "AUDIT: action=%s user=%s company=%s target=%s:%s",
        action,
        user,
        company,
        target_model,
        target_id,
    )
    return entry


def log_login_success(user, ip_address: str | None = None):
    return log_audit(
        action=AuditAction.LOGIN_SUCCESS,
        user=user,
        ip_address=ip_address,
        company=getattr(user, "company", None),
        details={"username": user.username},
    )


def log_login_failed(username: str, ip_address: str | None = None):
    return log_audit(
        action=AuditAction.LOGIN_FAILED,
        ip_address=ip_address,
        details={"username": username},
    )


def log_data_change(*, action: str, user, company, target_model: str, target_id, old_values: dict, new_values: dict):
    return log_audit(
        action=action,
        user=user,
        company=company,
        target_model=target_model,
        target_id=target_id,
        details={"old": old_values, "new": new_values},
    )


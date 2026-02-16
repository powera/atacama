"""Data-access helpers for Trakaido classroom models."""

from typing import List

import constants
from sqlalchemy import select

from models.database import db


def _is_trakaido_enabled() -> bool:
    return constants.SERVICE == "trakaido"


def _get_trakaido_models():
    if not _is_trakaido_enabled():
        return None, None, None

    from trakaido.models import Classroom, ClassroomMembership, ClassroomRole

    return Classroom, ClassroomMembership, ClassroomRole


def is_class_manager(user_id: int, classroom_id: int) -> bool:
    """Return True if user is a manager in the classroom."""
    _, ClassroomMembership, ClassroomRole = _get_trakaido_models()
    if ClassroomMembership is None or ClassroomRole is None:
        return False

    with db.session() as db_session:
        stmt = select(ClassroomMembership.id).where(
            ClassroomMembership.user_id == user_id,
            ClassroomMembership.classroom_id == classroom_id,
            ClassroomMembership.role == ClassroomRole.MANAGER,
        )
        return db_session.execute(stmt).scalar_one_or_none() is not None


def get_user_classrooms(user_id: int) -> List["Classroom"]:
    """Get classrooms a user belongs to."""
    Classroom, ClassroomMembership, _ = _get_trakaido_models()
    if Classroom is None or ClassroomMembership is None:
        return []

    with db.session() as db_session:
        stmt = (
            select(Classroom)
            .join(
                ClassroomMembership,
                ClassroomMembership.classroom_id == Classroom.id,
            )
            .where(ClassroomMembership.user_id == user_id)
            .order_by(Classroom.created_at.desc())
        )
        return db_session.execute(stmt).scalars().all()


def get_class_members(classroom_id: int) -> List["ClassroomMembership"]:
    """Get classroom members ordered by role and join time."""
    _, ClassroomMembership, _ = _get_trakaido_models()
    if ClassroomMembership is None:
        return []

    with db.session() as db_session:
        stmt = (
            select(ClassroomMembership)
            .where(ClassroomMembership.classroom_id == classroom_id)
            .order_by(ClassroomMembership.role.asc(), ClassroomMembership.joined_at.asc())
        )
        return db_session.execute(stmt).scalars().all()

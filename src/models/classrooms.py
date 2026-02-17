"""Data-access helpers for Trakaido classroom models."""

from typing import Any, Dict, List

import constants
from sqlalchemy import func, select

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


def get_user_classroom_capabilities(user_id: int) -> Dict[str, Any]:
    """Get classroom capability metadata for a user.

    Returns a compact payload suitable for auth/status endpoints.
    """
    Classroom, ClassroomMembership, ClassroomRole = _get_trakaido_models()
    if Classroom is None or ClassroomMembership is None or ClassroomRole is None:
        return {
            "is_class_manager": False,
            "managed_classrooms": [],
            "member_classrooms": [],
        }

    with db.session() as db_session:
        member_count_subquery = (
            select(
                ClassroomMembership.classroom_id,
                func.count(ClassroomMembership.id).label("member_count"),
            )
            .group_by(ClassroomMembership.classroom_id)
            .subquery()
        )

        stmt = (
            select(
                Classroom.id,
                Classroom.name,
                ClassroomMembership.role,
                member_count_subquery.c.member_count,
            )
            .join(
                ClassroomMembership,
                ClassroomMembership.classroom_id == Classroom.id,
            )
            .join(
                member_count_subquery,
                member_count_subquery.c.classroom_id == Classroom.id,
            )
            .where(ClassroomMembership.user_id == user_id)
            .order_by(Classroom.created_at.desc())
        )

        managed_classrooms: List[Dict[str, Any]] = []
        member_classrooms: List[Dict[str, Any]] = []

        for classroom_id, classroom_name, role, member_count in db_session.execute(stmt).all():
            classroom_payload = {
                "id": classroom_id,
                "display_name": classroom_name,
                "member_count": int(member_count or 0),
            }

            if role == ClassroomRole.MANAGER:
                managed_classrooms.append(classroom_payload)
            else:
                member_classrooms.append(classroom_payload)

        return {
            "is_class_manager": len(managed_classrooms) > 0,
            "managed_classrooms": managed_classrooms,
            "member_classrooms": member_classrooms,
        }

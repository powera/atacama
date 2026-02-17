"""Classroom manager stats endpoints.

These routes provide manager/admin access to normalized per-member summaries
that use the same metric calculators as self-service endpoints.
"""

from typing import Any, Dict, List, Optional, Tuple

from flask import jsonify, render_template, request, g
from flask.typing import ResponseReturnValue
from sqlalchemy import func, select

from atacama.decorators.auth import require_admin, require_auth
from models.database import db
from models.models import User
from trakaido.blueprints.shared import trakaido_bp, logger
from trakaido.blueprints.stats_backend import (
    calculate_daily_progress,
    calculate_weekly_progress,
    calculate_monthly_progress,
)
from trakaido.blueprints.stats_metrics import (
    build_activity_summary_from_totals,
    compute_member_summary,
)
from trakaido.models import Classroom, ClassroomMembership, ClassroomRole


CLASSROOM_STATS_API_DOCS = {
    "GET /api/trakaido/classroom_stats/member/<user_id>": "Get normalized stats summary for one classroom member",
    "POST /api/trakaido/classroom_stats/members": "Get normalized stats summaries for multiple classroom members",
    "GET /api/trakaido/classrooms/": "HTML list of user classrooms and role",
    "GET /api/trakaido/classrooms/<classroom_id>/members": "HTML classroom members list (manager only)",
    "GET /api/trakaido/classrooms/<classroom_id>/stats/daily": "HTML classroom daily aggregate stats (manager only)",
    "GET /api/trakaido/classrooms/<classroom_id>/stats/weekly": "HTML classroom weekly aggregate stats (manager only)",
    "GET /api/trakaido/classrooms/<classroom_id>/stats/monthly": "HTML classroom monthly aggregate stats (manager only)",
    "GET /api/trakaido/classrooms/<classroom_id>/members/<user_id>/stats": "HTML member stats detail (manager only)",
    "GET /api/trakaido/admin/users/search": "Admin user search by email",
    "POST /api/trakaido/admin/classrooms": "Admin create student group (classroom)",
    "POST /api/trakaido/admin/classrooms/<classroom_id>/members": "Admin add member by email",
    "POST /api/trakaido/admin/classrooms/<classroom_id>/members/remove": "Admin remove member by email",
}


def _normalize_email(value: Optional[str]) -> str:
    return (value or "").strip().lower()


def _classroom_payload(classroom: Classroom) -> Dict[str, Any]:
    return {
        "id": classroom.id,
        "name": classroom.name,
        "archived": classroom.archived,
        "createdByUserId": classroom.created_by_user_id,
        "createdAt": classroom.created_at,
    }


def _membership_payload(user: User, membership: ClassroomMembership) -> Dict[str, Any]:
    role = membership.role.value if hasattr(membership.role, "value") else str(membership.role)
    return {
        "userId": user.id,
        "email": user.email,
        "name": user.name,
        "role": role,
        "joinedAt": membership.joined_at,
    }


def _get_user_classrooms_with_role(user_id: int) -> List[Dict[str, Any]]:
    with db.session() as db_session:
        stmt = (
            select(
                Classroom.id,
                Classroom.name,
                Classroom.archived,
                Classroom.created_at,
                ClassroomMembership.role,
            )
            .join(ClassroomMembership, ClassroomMembership.classroom_id == Classroom.id)
            .where(ClassroomMembership.user_id == user_id)
            .order_by(Classroom.created_at.desc())
        )
        rows = db_session.execute(stmt).all()

    return [
        {
            "id": row.id,
            "name": row.name,
            "archived": row.archived,
            "createdAt": row.created_at,
            "role": row.role.value if hasattr(row.role, "value") else str(row.role),
        }
        for row in rows
    ]


def _get_classroom_membership_role(user_id: int, classroom_id: int) -> Optional[str]:
    with db.session() as db_session:
        stmt = select(ClassroomMembership.role).where(
            ClassroomMembership.user_id == user_id,
            ClassroomMembership.classroom_id == classroom_id,
        )
        role = db_session.execute(stmt).scalar_one_or_none()

    if role is None:
        return None
    return role.value if hasattr(role, "value") else str(role)


def _require_classroom_manager(user_id: int, classroom_id: int) -> Tuple[Optional[ResponseReturnValue], Optional[Dict[str, Any]]]:
    role = _get_classroom_membership_role(user_id, classroom_id)
    if role is None:
        return (jsonify({"error": "Classroom not found for current user"}), 404), None

    with db.session() as db_session:
        manager_stmt = select(ClassroomMembership.id).where(
            ClassroomMembership.user_id == user_id,
            ClassroomMembership.classroom_id == classroom_id,
            ClassroomMembership.role == ClassroomRole.MANAGER,
        )
        is_manager = db_session.execute(manager_stmt).scalar_one_or_none() is not None

    if not is_manager:
        return (jsonify({"error": "Manager access required"}), 403), None

    with db.session() as db_session:
        classroom = db_session.get(Classroom, classroom_id)
        if classroom is None:
            return (jsonify({"error": "Classroom not found"}), 404), None
        classroom_data = {
            "id": classroom.id,
            "name": classroom.name,
            "archived": classroom.archived,
            "createdAt": classroom.created_at,
        }

    return None, classroom_data


def _get_classroom_member_rows(classroom_id: int) -> List[Dict[str, Any]]:
    with db.session() as db_session:
        stmt = (
            select(ClassroomMembership, User)
            .join(User, User.id == ClassroomMembership.user_id)
            .where(ClassroomMembership.classroom_id == classroom_id)
            .order_by(ClassroomMembership.role.asc(), ClassroomMembership.joined_at.asc())
        )
        rows = db_session.execute(stmt).all()

    members: List[Dict[str, Any]] = []
    for membership, user in rows:
        role = membership.role.value if hasattr(membership.role, "value") else str(membership.role)
        members.append(
            {
                "userId": str(user.id),
                "name": user.name or user.email,
                "email": user.email,
                "role": role,
                "joinedAt": membership.joined_at,
            }
        )
    return members


def _get_user_by_email(db_session: Any, email: str) -> Optional[User]:
    normalized_email = _normalize_email(email)
    if not normalized_email:
        return None

    stmt = select(User).where(func.lower(User.email) == normalized_email)
    return db_session.execute(stmt).scalar_one_or_none()


def _extract_progress(progress_payload: Dict[str, Any], period: str) -> Dict[str, Any]:
    if period == "monthly":
        return progress_payload.get("monthlyAggregate", {})
    return progress_payload.get("progress", {})


def _aggregate_classroom_period_stats(members: List[Dict[str, Any]], language: str, period: str) -> Dict[str, Any]:
    period_calc = {
        "daily": calculate_daily_progress,
        "weekly": calculate_weekly_progress,
        "monthly": calculate_monthly_progress,
    }[period]

    by_activity_totals = {
        "directPractice": {},
        "contextualExposure": {},
    }
    aggregate = {
        "membersCount": len(members),
        "wordsKnown": 0,
        "wordsExposed": 0,
        "wordsTracked": 0,
        "delta": {
            "exposed": {"new": 0, "total": 0},
            "directPractice": {},
            "contextualExposure": {},
        },
    }

    member_breakdown: List[Dict[str, Any]] = []

    for member in members:
        user_id = member["userId"]
        summary = compute_member_summary(user_id, language)
        progress_payload = period_calc(user_id, language)
        period_delta = _extract_progress(progress_payload, period)

        if period_delta.get("error"):
            member_breakdown.append(
                {
                    "member": member,
                    "summary": summary,
                    "periodDelta": {},
                    "error": period_delta["error"],
                }
            )
            continue

        aggregate["wordsKnown"] += summary.get("wordsKnown", 0)
        aggregate["wordsExposed"] += summary.get("wordsExposed", 0)
        aggregate["wordsTracked"] += summary.get("wordsTracked", 0)

        exposed = period_delta.get("exposed", {})
        aggregate["delta"]["exposed"]["new"] += exposed.get("new", 0)
        aggregate["delta"]["exposed"]["total"] += exposed.get("total", 0)

        for category in ("directPractice", "contextualExposure"):
            cat_delta = period_delta.get(category, {})
            for activity, counters in cat_delta.items():
                by_activity_totals[category].setdefault(activity, {"correct": 0, "incorrect": 0})
                by_activity_totals[category][activity]["correct"] += counters.get("correct", 0)
                by_activity_totals[category][activity]["incorrect"] += counters.get("incorrect", 0)

        member_breakdown.append(
            {
                "member": member,
                "summary": summary,
                "periodDelta": period_delta,
                "periodMeta": {
                    "currentDay": progress_payload.get("currentDay"),
                    "targetBaselineDay": progress_payload.get("targetBaselineDay"),
                    "actualBaselineDay": progress_payload.get("actualBaselineDay"),
                },
            }
        )

    aggregate["activitySummary"] = build_activity_summary_from_totals(by_activity_totals)
    aggregate["delta"]["directPractice"] = by_activity_totals["directPractice"]
    aggregate["delta"]["contextualExposure"] = by_activity_totals["contextualExposure"]

    return {
        "aggregate": aggregate,
        "members": member_breakdown,
    }


@trakaido_bp.route('/api/trakaido/classrooms/', methods=['GET'])
@require_auth
def get_user_classrooms_html() -> ResponseReturnValue:
    """Render classrooms list for the authenticated user."""
    user_id = int(g.user.id)
    classrooms = _get_user_classrooms_with_role(user_id)
    return render_template(
        'trakaido/classrooms_list.html',
        page_title='My Classrooms',
        classrooms=classrooms,
    )


@trakaido_bp.route('/api/trakaido/classrooms/<int:classroom_id>/members', methods=['GET'])
@require_auth
def get_classroom_members_html(classroom_id: int) -> ResponseReturnValue:
    """Render classroom member list (manager only)."""
    auth_error, classroom = _require_classroom_manager(int(g.user.id), classroom_id)
    if auth_error:
        return auth_error

    members = _get_classroom_member_rows(classroom_id)
    return render_template(
        'trakaido/classroom_members.html',
        page_title=f"{classroom['name']} · Members",
        classroom=classroom,
        members=members,
    )


@trakaido_bp.route('/api/trakaido/classrooms/<int:classroom_id>/stats/<period>', methods=['GET'])
@require_auth
def get_classroom_stats_html(classroom_id: int, period: str) -> ResponseReturnValue:
    """Render classroom aggregate period stats (manager only)."""
    if period not in {'daily', 'weekly', 'monthly'}:
        return jsonify({"error": "Invalid period. Use daily, weekly, or monthly."}), 400

    auth_error, classroom = _require_classroom_manager(int(g.user.id), classroom_id)
    if auth_error:
        return auth_error

    language = request.args.get('language', 'lithuanian')
    members = _get_classroom_member_rows(classroom_id)
    stats_payload = _aggregate_classroom_period_stats(members, language, period)

    return render_template(
        'trakaido/classroom_period_stats.html',
        page_title=f"{classroom['name']} · {period.capitalize()} stats",
        classroom=classroom,
        language=language,
        period=period,
        aggregate=stats_payload['aggregate'],
        members=stats_payload['members'],
    )


@trakaido_bp.route('/api/trakaido/classrooms/<int:classroom_id>/members/<int:user_id>/stats', methods=['GET'])
@require_auth
def get_classroom_member_stats_html(classroom_id: int, user_id: int) -> ResponseReturnValue:
    """Render one member detail stats page (manager only)."""
    auth_error, classroom = _require_classroom_manager(int(g.user.id), classroom_id)
    if auth_error:
        return auth_error

    language = request.args.get('language', 'lithuanian')
    members = _get_classroom_member_rows(classroom_id)
    member = next((m for m in members if int(m['userId']) == user_id), None)
    if member is None:
        return jsonify({"error": "User is not a member of this classroom"}), 404

    summary = compute_member_summary(str(user_id), language)
    daily = calculate_daily_progress(str(user_id), language)
    weekly = calculate_weekly_progress(str(user_id), language)
    monthly = calculate_monthly_progress(str(user_id), language)

    return render_template(
        'trakaido/classroom_member_stats.html',
        page_title=f"{classroom['name']} · {member['name']} stats",
        classroom=classroom,
        language=language,
        member=member,
        summary=summary,
        daily=daily,
        weekly=weekly,
        monthly=monthly,
    )


@trakaido_bp.route('/api/trakaido/classroom_stats/member/<user_id>', methods=['GET'])
@require_admin
def get_classroom_member_summary(user_id: str) -> ResponseReturnValue:
    """Get normalized summary for one member.

    Query params:
    - language (optional): defaults to lithuanian
    """
    try:
        language = request.args.get("language", "lithuanian")
        return jsonify(compute_member_summary(str(user_id), language))
    except Exception as e:
        logger.error(f"Error getting classroom member summary for user {user_id}: {str(e)}")
        return jsonify({"error": str(e)}), 500


@trakaido_bp.route('/api/trakaido/classroom_stats/members', methods=['POST'])
@require_admin
def get_classroom_members_summary() -> ResponseReturnValue:
    """Get normalized summaries for multiple members in one request.

    Request body:
    {
        "userIds": ["123", "456"],
        "language": "lithuanian"
    }
    """
    try:
        data = request.get_json() or {}
        user_ids = data.get("userIds", [])
        language = data.get("language", "lithuanian")

        if not isinstance(user_ids, list) or not user_ids:
            return jsonify({"error": "Field 'userIds' must be a non-empty array"}), 400

        summaries = []
        errors = []

        for user_id in user_ids:
            try:
                summaries.append(compute_member_summary(str(user_id), language))
            except Exception as member_error:
                errors.append({"userId": str(user_id), "error": str(member_error)})

        return jsonify({
            "language": language,
            "memberCount": len(summaries),
            "members": summaries,
            "errors": errors,
        })
    except Exception as e:
        logger.error(f"Error getting classroom member summaries: {str(e)}")
        return jsonify({"error": str(e)}), 500


@trakaido_bp.route('/api/trakaido/admin/users/search', methods=['GET'])
@require_admin
def admin_search_users_by_email() -> ResponseReturnValue:
    """Admin lookup endpoint for users by partial email match."""
    email_query = _normalize_email(request.args.get("email"))
    if len(email_query) < 2:
        return jsonify({"error": "Query param 'email' must be at least 2 characters"}), 400

    raw_limit = request.args.get("limit", "20")
    try:
        limit = max(1, min(int(raw_limit), 100))
    except ValueError:
        return jsonify({"error": "Query param 'limit' must be an integer"}), 400

    with db.session() as db_session:
        stmt = (
            select(User)
            .where(func.lower(User.email).contains(email_query))
            .order_by(User.email.asc())
            .limit(limit)
        )
        users = db_session.execute(stmt).scalars().all()

    return jsonify({
        "count": len(users),
        "users": [
            {
                "id": user.id,
                "email": user.email,
                "name": user.name,
            }
            for user in users
        ],
    })


@trakaido_bp.route('/api/trakaido/admin/classrooms', methods=['POST'])
@require_admin
def admin_create_classroom() -> ResponseReturnValue:
    """Admin endpoint to create a student group (classroom)."""
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    manager_email = _normalize_email(data.get("managerEmail"))

    if not name:
        return jsonify({"error": "Field 'name' is required"}), 400

    with db.session() as db_session:
        manager_user = _get_user_by_email(db_session, manager_email) if manager_email else None
        if manager_email and manager_user is None:
            return jsonify({"error": f"No user found with email '{manager_email}'"}), 404

        creator_user = _get_user_by_email(db_session, g.user.email)
        if creator_user is None:
            return jsonify({"error": "Authenticated admin user not found"}), 404

        classroom = Classroom(
            name=name,
            created_by_user_id=creator_user.id,
        )
        db_session.add(classroom)
        db_session.flush()

        db_session.add(
            ClassroomMembership(
                classroom_id=classroom.id,
                user_id=creator_user.id,
                role=ClassroomRole.MANAGER,
            )
        )

        if manager_user and manager_user.id != creator_user.id:
            db_session.add(
                ClassroomMembership(
                    classroom_id=classroom.id,
                    user_id=manager_user.id,
                    role=ClassroomRole.MANAGER,
                )
            )

        classroom_payload = _classroom_payload(classroom)

    return jsonify({
        "classroom": classroom_payload,
    }), 201


@trakaido_bp.route('/api/trakaido/admin/classrooms/<int:classroom_id>/members', methods=['POST'])
@require_admin
def admin_add_classroom_member(classroom_id: int) -> ResponseReturnValue:
    """Admin endpoint to add a member/manager to a classroom by email."""
    data = request.get_json() or {}
    email = _normalize_email(data.get("email"))
    role_value = (data.get("role") or ClassroomRole.MEMBER.value).strip().lower()

    if not email:
        return jsonify({"error": "Field 'email' is required"}), 400
    if role_value not in {ClassroomRole.MEMBER.value, ClassroomRole.MANAGER.value}:
        return jsonify({"error": "Field 'role' must be either 'member' or 'manager'"}), 400

    role = ClassroomRole(role_value)

    with db.session() as db_session:
        classroom = db_session.get(Classroom, classroom_id)
        if classroom is None:
            return jsonify({"error": "Classroom not found"}), 404

        user = _get_user_by_email(db_session, email)
        if user is None:
            return jsonify({"error": f"No user found with email '{email}'"}), 404

        stmt = select(ClassroomMembership).where(
            ClassroomMembership.classroom_id == classroom_id,
            ClassroomMembership.user_id == user.id,
        )
        existing_membership = db_session.execute(stmt).scalar_one_or_none()

        if existing_membership is None:
            existing_membership = ClassroomMembership(
                classroom_id=classroom_id,
                user_id=user.id,
                role=role,
            )
            db_session.add(existing_membership)
            db_session.flush()
            status_code = 201
        else:
            existing_membership.role = role
            status_code = 200

        classroom_payload = _classroom_payload(classroom)
        member_payload = _membership_payload(user, existing_membership)

    return jsonify({
        "classroom": classroom_payload,
        "member": member_payload,
    }), status_code


@trakaido_bp.route('/api/trakaido/admin/classrooms/<int:classroom_id>/members/remove', methods=['POST'])
@require_admin
def admin_remove_classroom_member(classroom_id: int) -> ResponseReturnValue:
    """Admin endpoint to remove a classroom member by email."""
    data = request.get_json() or {}
    email = _normalize_email(data.get("email"))
    if not email:
        return jsonify({"error": "Field 'email' is required"}), 400

    with db.session() as db_session:
        classroom = db_session.get(Classroom, classroom_id)
        if classroom is None:
            return jsonify({"error": "Classroom not found"}), 404

        user = _get_user_by_email(db_session, email)
        if user is None:
            return jsonify({"error": f"No user found with email '{email}'"}), 404

        stmt = select(ClassroomMembership).where(
            ClassroomMembership.classroom_id == classroom_id,
            ClassroomMembership.user_id == user.id,
        )
        membership = db_session.execute(stmt).scalar_one_or_none()
        if membership is None:
            return jsonify({"error": "User is not a member of this classroom"}), 404

        if membership.role == ClassroomRole.MANAGER:
            manager_count_stmt = select(func.count(ClassroomMembership.id)).where(
                ClassroomMembership.classroom_id == classroom_id,
                ClassroomMembership.role == ClassroomRole.MANAGER,
            )
            manager_count = db_session.execute(manager_count_stmt).scalar_one()
            if manager_count <= 1:
                return jsonify({"error": "Cannot remove the last classroom manager"}), 400

        removed_member_payload = _membership_payload(user, membership)
        db_session.delete(membership)
        classroom_payload = _classroom_payload(classroom)

    return jsonify({
        "classroom": classroom_payload,
        "removed": removed_member_payload,
    })

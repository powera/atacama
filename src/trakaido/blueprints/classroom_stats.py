"""Classroom manager stats endpoints.

These routes provide manager/admin access to normalized per-member summaries
that use the same metric calculators as self-service endpoints.
"""

import json
import os
from functools import lru_cache
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import constants
from flask import jsonify, render_template, request, g
from flask.typing import ResponseReturnValue
from sqlalchemy import func, select

from atacama.decorators.auth import require_admin, require_auth
from common.config.language_config import get_language_manager
from models.database import db
from models.models import User
from trakaido.blueprints.shared import trakaido_bp, logger
from trakaido.blueprints.stats_backend import (
    calculate_daily_progress,
    calculate_monthly_progress,
    calculate_weekly_progress,
    get_journey_stats,
)
from trakaido.blueprints.stats_metrics import (
    build_activity_summary_from_totals,
    compute_member_summary,
)
from trakaido.models import Classroom, ClassroomMembership, ClassroomRole


CLASSROOM_STATS_API_DOCS = {
    "GET /api/trakaido/classroom_stats/<language>/member/<user_id>": "Get normalized stats summary for one classroom member",
    "POST /api/trakaido/classroom_stats/<language>/members": "Get normalized stats summaries for multiple classroom members",
    "GET /api/trakaido/classrooms/": "HTML list of user classrooms and role",
    "GET /api/trakaido/classrooms/<classroom_id>/members": "HTML classroom members list (manager only)",
    "GET /api/trakaido/classrooms/<classroom_id>/stats/<language>/daily": "HTML classroom daily aggregate stats (manager only)",
    "GET /api/trakaido/classrooms/<classroom_id>/stats/<language>/weekly": "HTML classroom weekly aggregate stats (manager only)",
    "GET /api/trakaido/classrooms/<classroom_id>/stats/<language>/monthly": "HTML classroom monthly aggregate stats (manager only)",
    "GET /api/trakaido/classrooms/<classroom_id>/members/<user_id>/stats/<language>": "HTML member stats detail (manager only)",
    "GET /api/trakaido/admin/users/search": "Admin user search by email",
    "GET /api/trakaido/admin/classrooms": "Admin HTML page: list all classrooms, create new",
    "GET /api/trakaido/admin/classrooms/<classroom_id>": "Admin HTML page: manage classroom members",
    "POST /api/trakaido/admin/classrooms": "Admin create student group (classroom)",
    "POST /api/trakaido/admin/classrooms/<classroom_id>/members": "Admin add member by email",
    "POST /api/trakaido/admin/classrooms/<classroom_id>/members/remove": "Admin remove member by email",
}


def _normalize_email(value: Optional[str]) -> str:
    return (value or "").strip().lower()


def _validate_language(language: str) -> Optional[ResponseReturnValue]:
    """Return a 400 error response if language is not a configured language key."""
    manager = get_language_manager()
    if language not in manager.get_all_language_keys():
        valid = ", ".join(sorted(manager.get_all_language_keys()))
        return jsonify({"error": f"Unknown language '{language}'. Valid options: {valid}"}), 400
    return None


def _get_language_display_name(language: str) -> str:
    manager = get_language_manager()
    config = manager.get_language_config(language)
    return config.name


def _get_user_active_languages(user_id: str) -> List[str]:
    """Return language keys for which the user has any stats data on disk.

    Uses a lightweight directory-existence check rather than loading stats.
    Languages are returned in configured order (matches languages.toml).
    """
    manager = get_language_manager()
    active = []
    for language_key in manager.get_all_language_keys():
        user_dir = os.path.join(constants.DATA_DIR, "trakaido", str(user_id), language_key)
        try:
            if os.path.isdir(user_dir) and any(os.scandir(user_dir)):
                active.append(language_key)
        except OSError:
            pass
    return active


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


def _build_monthly_questions_series(monthly: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Build privacy-preserving daily question totals for chart rendering."""
    daily_data = monthly.get("dailyData", [])
    if not isinstance(daily_data, list):
        return []

    chart_points: List[Dict[str, Any]] = []
    for row in daily_data:
        date_value = str(row.get("date", ""))
        questions_answered = int(row.get("questionsAnswered", 0) or 0)
        day_label = date_value[5:] if len(date_value) >= 10 else date_value
        chart_points.append(
            {
                "date": date_value,
                "dayLabel": day_label,
                "questionsAnswered": max(0, questions_answered),
            }
        )

    return chart_points


def _get_wireword_dir(language: str) -> Optional[str]:
    manager = get_language_manager()
    language_config = manager.get_language_config(language)
    lang_code = language_config.code
    wireword_dir = os.path.join(
        constants.DATA_DIR,
        "trakaido_wordlists",
        f"lang_{lang_code}",
        "generated",
        "wireword",
    )
    if not os.path.isdir(wireword_dir):
        return None
    return wireword_dir


def _build_word_label(target_word: str, english: str) -> str:
    if target_word and english:
        return f"{target_word} — {english}"
    return target_word or english


def _first_nonempty_str(entry: Dict[str, Any], keys: List[str]) -> str:
    for key in keys:
        value = str(entry.get(key, "")).strip()
        if value:
            return value
    return ""


@lru_cache(maxsize=32)
def _load_guid_word_labels(language: str) -> Dict[str, str]:
    """Load guid -> word labels from wireword files for a language."""
    wireword_dir = _get_wireword_dir(language)
    if wireword_dir is None:
        return {}

    labels: Dict[str, str] = {}

    for filename in sorted(os.listdir(wireword_dir)):
        if not filename.endswith(".json"):
            continue

        file_path = os.path.join(wireword_dir, filename)
        try:
            with open(file_path, "r", encoding="utf-8") as infile:
                file_data = json.load(infile)
        except Exception as exc:
            logger.warning(f"Failed to load wireword file {file_path}: {exc}")
            continue

        if not isinstance(file_data, list):
            continue

        for entry in file_data:
            if not isinstance(entry, dict):
                continue

            guid = str(entry.get("guid", "")).strip()
            if not guid:
                continue

            base_target = _first_nonempty_str(
                entry,
                [
                    "base_target",
                    "target",
                    "base_lithuanian",
                    "lithuanian",
                    "base_french",
                    "french",
                    "base_chinese",
                    "chinese",
                ],
            )
            base_english = _first_nonempty_str(entry, ["base_english", "english"])
            base_label = _build_word_label(base_target, base_english)
            if base_label:
                labels.setdefault(guid, base_label)

            grammatical_forms = entry.get("grammatical_forms", {})
            if not isinstance(grammatical_forms, dict):
                continue

            for form_key, form_data in grammatical_forms.items():
                if not isinstance(form_data, dict):
                    continue
                form_target = _first_nonempty_str(
                    form_data,
                    ["target", "lithuanian", "french", "chinese"],
                )
                form_label = _build_word_label(
                    form_target,
                    str(form_data.get("english", "")).strip(),
                )
                if not form_label:
                    continue
                labels.setdefault(f"{guid}_{form_key}", form_label)

    return labels


def _resolve_word_label(word_key: str, language: str) -> str:
    labels = _load_guid_word_labels(language)
    return labels.get(word_key, word_key)


def _get_recent_words(user_id: str, language: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Return the most recently seen words with day-level timestamps only."""
    journey_stats = get_journey_stats(user_id, language)
    stats = journey_stats.stats.get("stats", {})

    recents: List[Dict[str, Any]] = []
    for word_key, word_stats in stats.items():
        practice_history = word_stats.get("practiceHistory", {})
        last_seen = practice_history.get("lastSeen")
        if not last_seen:
            continue

        total_answers = 0
        for category in ("directPractice", "contextualExposure"):
            category_data = word_stats.get(category, {})
            if not isinstance(category_data, dict):
                continue
            for activity_data in category_data.values():
                if isinstance(activity_data, dict):
                    total_answers += int(activity_data.get("correct", 0) or 0)
                    total_answers += int(activity_data.get("incorrect", 0) or 0)

        last_seen_value = float(last_seen)
        if last_seen_value > 1_000_000_000_000:
            last_seen_value = last_seen_value / 1000.0

        last_seen_day = datetime.fromtimestamp(last_seen_value, tz=timezone.utc).date().isoformat()
        recents.append(
            {
                "wordKey": word_key,
                "wordLabel": _resolve_word_label(word_key, language),
                "lastSeenDay": last_seen_day,
                "totalAnswered": total_answers,
                "_lastSeenEpoch": last_seen_value,
            }
        )

    recents.sort(key=lambda item: item["_lastSeenEpoch"], reverse=True)
    for row in recents:
        row.pop("_lastSeenEpoch", None)
    return recents[:limit]


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


def _require_classroom_manager(
    user_id: int, classroom_id: int
) -> Tuple[Optional[ResponseReturnValue], Optional[Dict[str, Any]]]:
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


def _aggregate_classroom_period_stats(
    members: List[Dict[str, Any]], language: str, period: str
) -> Dict[str, Any]:
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


@trakaido_bp.route("/api/trakaido/classrooms/", methods=["GET"])
@require_auth
def get_user_classrooms_html() -> ResponseReturnValue:
    """Render classrooms list for the authenticated user."""
    user_id = int(g.user.id)
    classrooms = _get_user_classrooms_with_role(user_id)
    language = getattr(g, "current_language", "lithuanian")
    return render_template(
        "trakaido/classrooms_list.html",
        page_title="My Classrooms",
        classrooms=classrooms,
        language=language,
    )


@trakaido_bp.route("/api/trakaido/classrooms/<int:classroom_id>/members", methods=["GET"])
@require_auth
def get_classroom_members_html(classroom_id: int) -> ResponseReturnValue:
    """Render classroom member list (manager only)."""
    auth_error, classroom = _require_classroom_manager(int(g.user.id), classroom_id)
    if auth_error:
        return auth_error

    members = _get_classroom_member_rows(classroom_id)
    language = getattr(g, "current_language", "lithuanian")

    manager = get_language_manager()
    language_names = {
        k: manager.get_language_config(k).name for k in manager.get_all_language_keys()
    }
    for member in members:
        member["activeLanguages"] = _get_user_active_languages(str(member["userId"]))

    return render_template(
        "trakaido/classroom_members.html",
        page_title=f"{classroom['name']} · Members",
        classroom=classroom,
        members=members,
        language=language,
        language_names=language_names,
    )


@trakaido_bp.route(
    "/api/trakaido/classrooms/<int:classroom_id>/stats/<language>/<period>", methods=["GET"]
)
@require_auth
def get_classroom_stats_html(classroom_id: int, language: str, period: str) -> ResponseReturnValue:
    """Render classroom aggregate period stats (manager only)."""
    lang_error = _validate_language(language)
    if lang_error:
        return lang_error

    if period not in {"daily", "weekly", "monthly"}:
        return jsonify({"error": "Invalid period. Use daily, weekly, or monthly."}), 400

    auth_error, classroom = _require_classroom_manager(int(g.user.id), classroom_id)
    if auth_error:
        return auth_error

    members = _get_classroom_member_rows(classroom_id)
    stats_payload = _aggregate_classroom_period_stats(members, language, period)

    return render_template(
        "trakaido/classroom_period_stats.html",
        page_title=f"{classroom['name']} · {period.capitalize()} stats",
        classroom=classroom,
        language=language,
        period=period,
        aggregate=stats_payload["aggregate"],
        members=stats_payload["members"],
    )


@trakaido_bp.route(
    "/api/trakaido/classrooms/<int:classroom_id>/members/<int:user_id>/stats/<language>",
    methods=["GET"],
)
@require_auth
def get_classroom_member_stats_html(
    classroom_id: int, user_id: int, language: str
) -> ResponseReturnValue:
    """Render one member detail stats page (manager only)."""
    lang_error = _validate_language(language)
    if lang_error:
        return lang_error

    auth_error, classroom = _require_classroom_manager(int(g.user.id), classroom_id)
    if auth_error:
        return auth_error

    members = _get_classroom_member_rows(classroom_id)
    member = next((m for m in members if int(m["userId"]) == user_id), None)
    if member is None:
        return jsonify({"error": "User is not a member of this classroom"}), 404

    summary = compute_member_summary(str(user_id), language)
    daily = calculate_daily_progress(str(user_id), language)
    weekly = calculate_weekly_progress(str(user_id), language)
    monthly = calculate_monthly_progress(str(user_id), language)
    monthly_questions_series = _build_monthly_questions_series(monthly)
    recent_words = _get_recent_words(str(user_id), language)

    return render_template(
        "trakaido/classroom_member_stats.html",
        page_title=f"{classroom['name']} · {member['name']} stats",
        classroom=classroom,
        language=language,
        language_display_name=_get_language_display_name(language),
        member=member,
        summary=summary,
        daily=daily,
        weekly=weekly,
        monthly=monthly,
        monthly_questions_series=monthly_questions_series,
        recent_words=recent_words,
    )


@trakaido_bp.route("/api/trakaido/classroom_stats/<language>/member/<user_id>", methods=["GET"])
@require_admin
def get_classroom_member_summary(language: str, user_id: str) -> ResponseReturnValue:
    """Get normalized summary for one member."""
    lang_error = _validate_language(language)
    if lang_error:
        return lang_error
    try:
        return jsonify(compute_member_summary(str(user_id), language))
    except Exception as e:
        logger.error(f"Error getting classroom member summary for user {user_id}: {str(e)}")
        return jsonify({"error": str(e)}), 500


@trakaido_bp.route("/api/trakaido/classroom_stats/<language>/members", methods=["POST"])
@require_admin
def get_classroom_members_summary(language: str) -> ResponseReturnValue:
    """Get normalized summaries for multiple members in one request.

    Request body:
    {
        "userIds": ["123", "456"]
    }
    """
    lang_error = _validate_language(language)
    if lang_error:
        return lang_error
    try:
        data = request.get_json() or {}
        user_ids = data.get("userIds", [])

        if not isinstance(user_ids, list) or not user_ids:
            return jsonify({"error": "Field 'userIds' must be a non-empty array"}), 400

        summaries = []
        errors = []

        for user_id in user_ids:
            try:
                summaries.append(compute_member_summary(str(user_id), language))
            except Exception as member_error:
                errors.append({"userId": str(user_id), "error": str(member_error)})

        return jsonify(
            {
                "language": language,
                "memberCount": len(summaries),
                "members": summaries,
                "errors": errors,
            }
        )
    except Exception as e:
        logger.error(f"Error getting classroom member summaries: {str(e)}")
        return jsonify({"error": str(e)}), 500


@trakaido_bp.route("/api/trakaido/admin/classrooms", methods=["GET"])
@require_admin
def admin_list_classrooms_html() -> ResponseReturnValue:
    """Admin HTML page: list all classrooms and create new ones."""
    with db.session() as db_session:
        stmt = select(Classroom).order_by(Classroom.created_at.desc())
        classrooms = db_session.execute(stmt).scalars().all()
        classroom_list = [_classroom_payload(c) for c in classrooms]

    return render_template(
        "trakaido/admin_classrooms.html",
        page_title="Admin · Classrooms",
        classrooms=classroom_list,
    )


@trakaido_bp.route("/api/trakaido/admin/classrooms/<int:classroom_id>", methods=["GET"])
@require_admin
def admin_classroom_detail_html(classroom_id: int) -> ResponseReturnValue:
    """Admin HTML page: view and manage classroom members."""
    with db.session() as db_session:
        classroom = db_session.get(Classroom, classroom_id)
        if classroom is None:
            return jsonify({"error": "Classroom not found"}), 404
        classroom_data = _classroom_payload(classroom)

    members = _get_classroom_member_rows(classroom_id)
    return render_template(
        "trakaido/admin_classroom_detail.html",
        page_title=f"Admin · {classroom_data['name']}",
        classroom=classroom_data,
        members=members,
    )


@trakaido_bp.route("/api/trakaido/admin/users/search", methods=["GET"])
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

    return jsonify(
        {
            "count": len(users),
            "users": [
                {
                    "id": user.id,
                    "email": user.email,
                    "name": user.name,
                }
                for user in users
            ],
        }
    )


@trakaido_bp.route("/api/trakaido/admin/classrooms", methods=["POST"])
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

    return (
        jsonify(
            {
                "classroom": classroom_payload,
            }
        ),
        201,
    )


@trakaido_bp.route("/api/trakaido/admin/classrooms/<int:classroom_id>/members", methods=["POST"])
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

    return (
        jsonify(
            {
                "classroom": classroom_payload,
                "member": member_payload,
            }
        ),
        status_code,
    )


@trakaido_bp.route(
    "/api/trakaido/admin/classrooms/<int:classroom_id>/members/remove", methods=["POST"]
)
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

    return jsonify(
        {
            "classroom": classroom_payload,
            "removed": removed_member_payload,
        }
    )

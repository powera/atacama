"""Classroom manager stats endpoints.

These routes provide manager/admin access to normalized per-member summaries
that use the same metric calculators as self-service endpoints.
"""

from flask import jsonify, request
from flask.typing import ResponseReturnValue

from atacama.decorators.auth import require_admin
from trakaido.blueprints.shared import trakaido_bp, logger
from trakaido.blueprints.stats_metrics import compute_member_summary


CLASSROOM_STATS_API_DOCS = {
    "GET /api/trakaido/classroom_stats/member/<user_id>": "Get normalized stats summary for one classroom member",
    "POST /api/trakaido/classroom_stats/members": "Get normalized stats summaries for multiple classroom members",
}


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

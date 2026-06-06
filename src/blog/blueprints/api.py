"""JSON submission API for external clients (e.g. the Atacama iOS app).

Provides token-authenticated JSON endpoints that mirror the form-based admin
submit flow:

- ``POST /api/messages`` creates a new message from JSON.
- ``GET /api/channels`` lists the channels the authenticated user may post to.

Both reuse the shared creation/archiving helpers in :mod:`blog.blueprints.shared`
so their behavior stays in sync with the admin form route.
"""

from flask import g, jsonify, request, url_for
from flask.typing import ResponseReturnValue

from common.base.logging_config import get_logger
from common.config.channel_config import get_channel_manager
from common.config.domain_config import get_domain_manager
from models import get_or_create_user, get_user_allowed_channels
from models.database import db
from atacama.blueprints.errors import handle_error
from atacama.decorators import require_auth
from blog.blueprints.shared import content_bp, create_email_message, start_archive_thread

logger = get_logger(__name__)


@content_bp.route("/api/atacama-config", methods=["GET"])
def client_config_api() -> ResponseReturnValue:
    """
    Self-describing config for the Atacama iOS client (unauthenticated discovery).

    The iOS app fetches this when a server is added so it can label the server and
    learn which authentication flow to use. The matching endpoint on the newslettr
    backend returns the same shape so one client can target either backend.

    :return: JSON with the site name, API base URL, auth flow, and capabilities
    """
    # ``g.domain_config`` is populated per request from the Host header by
    # ``before_request_handler``; fall back to the default config if absent.
    domain_config = getattr(g, "domain_config", None)
    if domain_config is None:
        domain_config = get_domain_manager().get_domain_config("default")

    return jsonify(
        {
            "name": domain_config.name,
            "description": domain_config.description,
            # ``url_root`` is the absolute base (scheme + host) ending in "/";
            # strip the trailing slash so the client can append "/api/...".
            "api_base": request.url_root.rstrip("/"),
            "auth": {"type": "oauth", "login_path": "/login"},
            "capabilities": {"preview": True, "messages": True, "channels": True},
        }
    )


@content_bp.route("/api/messages", methods=["POST"])
@require_auth
def create_message_api() -> ResponseReturnValue:
    """
    Create a new message (Email) from JSON.

    JSON equivalent of the form-based ``POST /admin/submit`` route, sharing the
    same creation and archiving pipeline. The author is resolved from ``g.user``,
    which :func:`require_auth` populates from either an auth token (mobile/API) or
    a session.

    Request JSON:
        - subject: The message subject (required)
        - content: The full AML content (required)
        - channel: Channel to post to (optional, defaults to the configured default)
        - parent_id: Optional parent message id for chains

    :return: JSON with new message id, url, and rendered HTML; HTTP 201 on success
    :raises: HTTP 400 if the request body is not JSON
    :raises: HTTP 422 if subject or content is missing
    :raises: HTTP 500 if creation fails
    """
    if not request.is_json:
        return handle_error("400", "Bad Request", "Request must be JSON")

    data = request.get_json(silent=True)
    if data is None:
        return handle_error("400", "Bad Request", "Request must be JSON")

    channel_manager = get_channel_manager()

    subject = (data.get("subject") or "").strip()
    content = (data.get("content") or "").strip()
    channel = data.get("channel") or channel_manager.default_channel
    if isinstance(channel, str):
        channel = channel.strip() or channel_manager.default_channel
    parent_id = data.get("parent_id")

    if not subject or not content:
        return handle_error("422", "Validation Error", "Subject and content are required")

    try:
        with db.session() as db_session:
            # Re-fetch the user inside this session to avoid detached-instance issues
            # (g.user may come from a token and a now-closed session).
            db_user = get_or_create_user(db_session, {"email": g.user.email, "name": g.user.name})

            message, extracted_urls = create_email_message(
                db_session,
                author=db_user,
                subject=subject,
                content=content,
                channel=channel,
                parent_id=parent_id,
            )

            db_session.commit()
            message_id = message.id
            processed_content = message.processed_content

        # Archive URLs and posts if archive service is enabled
        start_archive_thread(message_id, extracted_urls, channel)

        return (
            jsonify(
                {
                    "id": message_id,
                    "url": url_for("content.get_message", message_id=message_id, _external=True),
                    "processed_content": processed_content,
                }
            ),
            201,
        )

    except Exception as e:
        logger.error(f"Error creating message via API: {str(e)}")
        return handle_error("500", "Submission Error", "Failed to submit message", str(e))


@content_bp.route("/api/channels", methods=["GET"])
@require_auth
def list_channels_api() -> ResponseReturnValue:
    """
    List the channels the authenticated user may post to, for a channel picker.

    Honors system access levels and the user's channel preferences via
    :func:`get_user_allowed_channels`.

    :return: JSON with the list of channels and the default channel
    """
    channel_manager = get_channel_manager()

    allowed = get_user_allowed_channels(g.user)

    channels = []
    for name in allowed:
        config = channel_manager.get_channel_config(name)
        if not config:
            continue
        channels.append(
            {
                "name": name,
                "display_name": config.get_display_name(),
                "group": config.group,
                "requires_auth": config.requires_auth,
            }
        )

    return jsonify({"channels": channels, "default": channel_manager.default_channel})

"""Tests for the JSON submission API: POST /api/messages and GET /api/channels."""

import unittest
from datetime import datetime

from atacama.server import create_app
from models.database import db
from models.models import User, UserToken, Email


class SubmitApiTests(unittest.TestCase):
    """Test cases for the token-authenticated JSON submission endpoints."""

    def setUp(self):
        """Set up test application with in-memory database and an auth token."""
        self.app = create_app(testing=True)
        self.app.config.update(
            {
                "TESTING": True,
                "SERVER_NAME": "test.local",
            }
        )
        self.client = self.app.test_client()
        self.token = "api-test-token-12345"
        self.user_email = "api@example.com"

        with self.app.app_context():
            with db.session() as db_session:
                user = User(email=self.user_email, name="API User")
                db_session.add(user)
                db_session.flush()
                db_session.add(
                    UserToken(user_id=user.id, token=self.token, created_at=datetime.utcnow())
                )
                db_session.commit()

    def tearDown(self):
        """Clean up after tests."""
        db.cleanup()

    @property
    def auth_headers(self):
        return {"Authorization": f"Bearer {self.token}"}

    # --- POST /api/messages -------------------------------------------------

    def test_create_message_requires_auth(self):
        """Unauthenticated requests are rejected with 401 UNAUTHORIZED."""
        response = self.client.post("/api/messages", json={"subject": "Hi", "content": "Body"})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json().get("code"), "UNAUTHORIZED")

    def test_create_message_rejects_non_json(self):
        """Non-JSON bodies are rejected with 400."""
        response = self.client.post(
            "/api/messages",
            data="not json",
            content_type="text/plain",
            headers=self.auth_headers,
        )
        self.assertEqual(response.status_code, 400)

    def test_create_message_requires_subject_and_content(self):
        """Missing subject or content yields 422."""
        response = self.client.post(
            "/api/messages",
            json={"subject": "", "content": "Body"},
            headers=self.auth_headers,
        )
        self.assertEqual(response.status_code, 422)

        response = self.client.post(
            "/api/messages",
            json={"subject": "Subject only"},
            headers=self.auth_headers,
        )
        self.assertEqual(response.status_code, 422)

    def test_create_message_success(self):
        """A valid request creates a message and returns id, url, and HTML."""
        response = self.client.post(
            "/api/messages",
            json={"subject": "On deserts", "content": "Main text here.", "channel": "misc"},
            headers=self.auth_headers,
        )
        self.assertEqual(response.status_code, 201)
        data = response.get_json()
        self.assertIn("id", data)
        self.assertIn("processed_content", data)
        self.assertTrue(data["url"].endswith(f"/messages/{data['id']}"))

        # Verify the message was actually persisted with the right author/channel.
        with self.app.app_context():
            with db.session() as db_session:
                message = db_session.query(Email).get(data["id"])
                self.assertIsNotNone(message)
                self.assertEqual(message.subject, "On deserts")
                self.assertEqual(message.channel, "misc")
                self.assertEqual(message.author.email, self.user_email)
                self.assertTrue(message.processed_content)
                self.assertTrue(message.preview_content)

    def test_create_message_defaults_channel(self):
        """Omitting channel falls back to the default channel."""
        response = self.client.post(
            "/api/messages",
            json={"subject": "No channel", "content": "Body"},
            headers=self.auth_headers,
        )
        self.assertEqual(response.status_code, 201)
        data = response.get_json()
        with self.app.app_context():
            with db.session() as db_session:
                message = db_session.query(Email).get(data["id"])
                self.assertEqual(message.channel, "private")  # default_channel

    def test_create_message_links_parent(self):
        """A valid parent_id links the new message into a chain."""
        parent = self.client.post(
            "/api/messages",
            json={"subject": "Parent", "content": "Parent body", "channel": "misc"},
            headers=self.auth_headers,
        )
        parent_id = parent.get_json()["id"]

        child = self.client.post(
            "/api/messages",
            json={
                "subject": "Child",
                "content": "Child body",
                "channel": "misc",
                "parent_id": parent_id,
            },
            headers=self.auth_headers,
        )
        self.assertEqual(child.status_code, 201)
        child_id = child.get_json()["id"]
        with self.app.app_context():
            with db.session() as db_session:
                message = db_session.query(Email).get(child_id)
                self.assertEqual(message.parent_id, parent_id)

    def test_create_message_ignores_invalid_parent(self):
        """An unknown/invalid parent_id is ignored, not fatal."""
        response = self.client.post(
            "/api/messages",
            json={"subject": "Orphan", "content": "Body", "channel": "misc", "parent_id": 999999},
            headers=self.auth_headers,
        )
        self.assertEqual(response.status_code, 201)
        with self.app.app_context():
            with db.session() as db_session:
                message = db_session.query(Email).get(response.get_json()["id"])
                self.assertIsNone(message.parent_id)

    # --- GET /api/channels --------------------------------------------------

    def test_list_channels_requires_auth(self):
        """Unauthenticated requests are rejected with 401."""
        response = self.client.get("/api/channels")
        self.assertEqual(response.status_code, 401)

    def test_list_channels_shape_and_filtering(self):
        """Returns allowed channels with the expected shape and a default."""
        response = self.client.get("/api/channels", headers=self.auth_headers)
        self.assertEqual(response.status_code, 200)
        data = response.get_json()

        self.assertEqual(data["default"], "private")
        self.assertIsInstance(data["channels"], list)

        by_name = {c["name"]: c for c in data["channels"]}
        # Public channel is available to every authenticated user.
        self.assertIn("misc", by_name)
        misc = by_name["misc"]
        self.assertEqual(misc["display_name"], "Miscellany")
        self.assertEqual(misc["group"], "General")
        self.assertFalse(misc["requires_auth"])

        # Restricted, admin-only channel is excluded for a regular user.
        self.assertNotIn("politics", by_name)


if __name__ == "__main__":
    unittest.main()

"""Tests for the shared-link API: POST /api/links (backs the iOS Share Extension)."""

import unittest
from datetime import datetime

from atacama.server import create_app
from models.database import db
from models.models import User, UserToken, Email


class LinksApiTests(unittest.TestCase):
    """Test cases for the token-authenticated shared-link endpoint."""

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
        self.token = "links-test-token-12345"
        self.user_email = "links@example.com"

        with self.app.app_context():
            with db.session() as db_session:
                user = User(email=self.user_email, name="Links User")
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

    def _message(self, message_id):
        with self.app.app_context():
            with db.session() as db_session:
                return db_session.query(Email).get(message_id)

    # --- Validation -----------------------------------------------------------

    def test_create_link_requires_auth(self):
        """Unauthenticated requests are rejected with 401 UNAUTHORIZED."""
        response = self.client.post("/api/links", json={"url": "https://example.com/a"})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json().get("code"), "UNAUTHORIZED")

    def test_create_link_rejects_non_json(self):
        """Non-JSON bodies are rejected with 400."""
        response = self.client.post(
            "/api/links",
            data="not json",
            content_type="text/plain",
            headers=self.auth_headers,
        )
        self.assertEqual(response.status_code, 400)

    def test_create_link_requires_url(self):
        """A missing URL yields 422."""
        response = self.client.post("/api/links", json={}, headers=self.auth_headers)
        self.assertEqual(response.status_code, 422)

    def test_create_link_rejects_invalid_url(self):
        """Non-http(s) or malformed URLs yield 422."""
        for bad in ("ftp://example.com/file", "not-a-url", "https://"):
            response = self.client.post("/api/links", json={"url": bad}, headers=self.auth_headers)
            self.assertEqual(response.status_code, 422, bad)

    def test_create_link_rejects_draft(self):
        """Atacama has no drafts; draft=true is rejected with a clear message."""
        response = self.client.post(
            "/api/links",
            json={"url": "https://example.com/a", "draft": True},
            headers=self.auth_headers,
        )
        self.assertEqual(response.status_code, 422)
        self.assertIn("draft", response.get_json()["message"].lower())

    def test_create_link_rejects_unknown_channel(self):
        """An unknown topic/channel yields 422."""
        response = self.client.post(
            "/api/links",
            json={"url": "https://example.com/a", "topic": "no-such-channel"},
            headers=self.auth_headers,
        )
        self.assertEqual(response.status_code, 422)

    def test_create_link_rejects_overlong_fields(self):
        """Field limits mirror the newslettr backend."""
        base = {"url": "https://example.com/a"}
        for overrides in (
            {"url": "https://example.com/" + "a" * 2000},
            {"title": "t" * 201},
            {"quote": "q" * 2001},
            {"comment": "c" * 2001},
        ):
            response = self.client.post(
                "/api/links", json={**base, **overrides}, headers=self.auth_headers
            )
            self.assertEqual(response.status_code, 422, overrides)

    # --- Creation -------------------------------------------------------------

    def test_create_link_bare_share(self):
        """A bare URL share succeeds: title falls back to the host, channel to default."""
        response = self.client.post(
            "/api/links",
            json={"url": "https://example.com/article"},
            headers=self.auth_headers,
        )
        self.assertEqual(response.status_code, 201)
        data = response.get_json()
        self.assertEqual(data["title"], "example.com")
        self.assertEqual(data["domain"], "example.com")
        self.assertEqual(data["url"], "https://example.com/article")
        self.assertFalse(data["is_draft"])
        self.assertEqual(data["topic"]["id"], "private")  # default_channel

        with self.app.app_context():
            with db.session() as db_session:
                message = db_session.query(Email).get(data["id"])
                self.assertIsNotNone(message)
                self.assertEqual(message.subject, "example.com")
                self.assertEqual(message.channel, "private")
                self.assertEqual(message.author.email, self.user_email)
                self.assertIn("https://example.com/article", message.content)
                self.assertTrue(message.processed_content)

    def test_create_link_full_share(self):
        """Title, quote, comment, and topic all land in the saved message."""
        response = self.client.post(
            "/api/links",
            json={
                "url": "https://example.com/article",
                "title": "Great read",
                "quote": "A pulled excerpt.",
                "comment": "Why it matters.",
                "topic": "misc",
            },
            headers=self.auth_headers,
        )
        self.assertEqual(response.status_code, 201)
        data = response.get_json()
        self.assertEqual(data["title"], "Great read")
        self.assertEqual(data["topic"]["id"], "misc")
        self.assertTrue(data["message_url"].endswith(f"/messages/{data['id']}"))

        message = self._message(data["id"])
        self.assertEqual(message.subject, "Great read")
        self.assertEqual(message.channel, "misc")
        self.assertIn("Why it matters.", message.content)
        self.assertIn("<quote> A pulled excerpt.", message.content)
        self.assertIn("https://example.com/article", message.content)
        # The comment (the sharer's voice) leads the composed message.
        self.assertTrue(message.content.startswith("Why it matters."))

    def test_create_link_accepts_channel_alias(self):
        """The atacama-style `channel` key is accepted as an alias for `topic`."""
        response = self.client.post(
            "/api/links",
            json={"url": "https://example.com/a", "channel": "misc"},
            headers=self.auth_headers,
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self._message(response.get_json()["id"]).channel, "misc")

    def test_config_advertises_links_capability(self):
        """GET /api/atacama-config advertises links so clients can discover support."""
        response = self.client.get("/api/atacama-config")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["capabilities"]["links"])


if __name__ == "__main__":
    unittest.main()

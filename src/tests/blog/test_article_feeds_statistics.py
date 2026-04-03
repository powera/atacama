"""Tests for article, feed, and statistics blog endpoints."""

import unittest
from datetime import datetime

from atacama.server import create_app
from models.database import db
from models.models import Article, Email, User


class ArticleFeedStatisticsTests(unittest.TestCase):
    """End-to-end tests for important blog endpoints."""

    def setUp(self):
        self.app = create_app(testing=True)
        self.app.config.update({"TESTING": True, "SERVER_NAME": "test.local"})
        self.client = self.app.test_client()

    def tearDown(self):
        db.cleanup()

    def create_user(self, email="blogger@example.com", name="Blogger"):
        with self.app.app_context():
            with db.session() as db_session:
                user = User(email=email, name=name)
                db_session.add(user)
                db_session.commit()
                return user.id

    def test_submit_and_view_article(self):
        """Submitting an article should persist and be viewable by slug."""
        user_id = self.create_user()

        with self.app.app_context():
            with db.session() as db_session:
                user = db_session.query(User).filter_by(id=user_id).first()
                with self.client.session_transaction() as sess:
                    sess["user"] = {"email": user.email, "name": user.name}

        response = self.client.post(
            "/submit/article",
            data={
                "title": "Coverage Article",
                "slug": "coverage-article",
                "content": "<green>Coverage matters</green>",
                "channel": "misc",
                "publish": "true",
            },
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/p/coverage-article", response.location)

        article_response = self.client.get("/p/coverage-article")
        self.assertEqual(article_response.status_code, 200)
        self.assertIn(b"Coverage Article", article_response.data)

    def test_rss_feed_excludes_private_messages(self):
        """RSS should include public channel content and exclude private content."""
        user_id = self.create_user("rss@example.com", "RSS User")

        with self.app.app_context():
            with db.session() as db_session:
                db_session.add_all(
                    [
                        Email(
                            author_id=user_id,
                            channel="misc",
                            subject="Public Entry",
                            content="public body",
                            processed_content="<p>public body</p>",
                        ),
                        Email(
                            author_id=user_id,
                            channel="private",
                            subject="Private Entry",
                            content="private body",
                            processed_content="<p>private body</p>",
                        ),
                    ]
                )
                db_session.commit()

        response = self.client.get("/feed.xml")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Public Entry", response.data)
        self.assertNotIn(b"Private Entry", response.data)

    def test_channel_statistics_endpoint(self):
        """Statistics page should render and include seeded channel data."""
        user_id = self.create_user("stats@example.com", "Stats User")

        with self.app.app_context():
            with db.session() as db_session:
                db_session.add(
                    Email(
                        author_id=user_id,
                        channel="misc",
                        subject="Stats Subject",
                        content="Stats Body",
                        processed_content="Stats Body",
                    )
                )
                db_session.commit()

        response = self.client.get("/stats")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Channel Statistics", response.data)
        self.assertIn(b"Miscellany", response.data)

    def test_article_stream_shows_only_published(self):
        """Channel article stream should only show published articles."""
        user_id = self.create_user("articles@example.com", "Article User")

        with self.app.app_context():
            with db.session() as db_session:
                db_session.add_all(
                    [
                        Article(
                            author_id=user_id,
                            channel="misc",
                            slug="published-article",
                            title="Published Article",
                            content="published",
                            processed_content="<p>published</p>",
                            published=True,
                            published_at=datetime.utcnow(),
                        ),
                        Article(
                            author_id=user_id,
                            channel="misc",
                            slug="draft-article",
                            title="Draft Article",
                            content="draft",
                            processed_content="<p>draft</p>",
                            published=False,
                        ),
                    ]
                )
                db_session.commit()

        response = self.client.get("/articles/channel/misc")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Published Article", response.data)
        self.assertNotIn(b"Draft Article", response.data)


if __name__ == "__main__":
    unittest.main()

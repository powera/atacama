"""Tests for classroom stats HTML routes."""

import os
import tempfile
import unittest
from unittest.mock import patch

import constants
from atacama.server import create_app
from models.database import db
from models.models import User, UserToken
from trakaido.models import Classroom, ClassroomMembership, ClassroomRole


class ClassroomStatsRoutesTests(unittest.TestCase):
    """Integration-style tests for classroom stats HTML endpoints."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.original_data_dir = constants.DATA_DIR
        constants.init_testing(test_db_path="sqlite:///:memory:", service="trakaido")
        constants.DATA_DIR = self.temp_dir
        db.cleanup()

        self.app = create_app(testing=True, blueprint_set="TRAKAIDO")
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

        with db.session() as session:
            self.manager = User(email="manager@example.com", name="Manager")
            self.member = User(email="member@example.com", name="Member")
            self.outsider = User(email="outsider@example.com", name="Outsider")
            self.admin = User(email="admin@example.com", name="Admin")
            session.add_all([self.manager, self.member, self.outsider, self.admin])
            session.flush()

            session.add_all(
                [
                    UserToken(user_id=self.manager.id, token="manager-token"),
                    UserToken(user_id=self.member.id, token="member-token"),
                    UserToken(user_id=self.outsider.id, token="outsider-token"),
                ]
            )

            classroom = Classroom(name="A1 Lithuanian", created_by_user_id=self.manager.id)
            session.add(classroom)
            session.flush()
            self.classroom_id = classroom.id

            session.add_all(
                [
                    ClassroomMembership(
                        classroom_id=classroom.id,
                        user_id=self.manager.id,
                        role=ClassroomRole.MANAGER,
                    ),
                    ClassroomMembership(
                        classroom_id=classroom.id,
                        user_id=self.member.id,
                        role=ClassroomRole.MEMBER,
                    ),
                ]
            )

    def tearDown(self):
        db.cleanup()
        self.app_context.pop()
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)
        constants.DATA_DIR = self.original_data_dir
        constants.reset()

    def _auth_headers(self, token: str):
        return {"Authorization": f"Bearer {token}"}

    def _set_admin_session(self):
        with self.client.session_transaction() as sess:
            sess["user"] = {
                "email": "admin@example.com",
                "name": "Admin",
            }

    def _admin_post(self, path: str, **kwargs):
        return self.client.post(path, base_url="https://trakaido.com", **kwargs)

    def _admin_get(self, path: str, **kwargs):
        return self.client.get(path, base_url="https://trakaido.com", **kwargs)

    def test_classrooms_page_renders_for_authenticated_user(self):
        response = self.client.get(
            "/api/trakaido/classrooms/", headers=self._auth_headers("manager-token")
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"My Classrooms", response.data)
        self.assertIn(b"A1 Lithuanian", response.data)

    def test_members_page_requires_manager_role(self):
        response = self.client.get(
            f"/api/trakaido/classrooms/{self.classroom_id}/members",
            headers=self._auth_headers("member-token"),
        )

        self.assertEqual(response.status_code, 403)
        self.assertIn(b"Manager access required", response.data)

    def test_members_page_shows_no_activity_when_no_stats_dirs(self):
        response = self.client.get(
            f"/api/trakaido/classrooms/{self.classroom_id}/members",
            headers=self._auth_headers("manager-token"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"No activity yet", response.data)

    def test_members_page_shows_language_links_for_active_languages(self):
        # Create a non-empty stats directory for the member in Lithuanian and Chinese
        for language in ("lithuanian", "chinese"):
            user_dir = os.path.join(self.temp_dir, "trakaido", str(self.member.id), language)
            os.makedirs(user_dir, exist_ok=True)
            open(os.path.join(user_dir, "stats.json"), "w").close()

        response = self.client.get(
            f"/api/trakaido/classrooms/{self.classroom_id}/members",
            headers=self._auth_headers("manager-token"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Lithuanian", response.data)
        self.assertIn(b"Chinese", response.data)
        # Member with activity should have language-specific links
        member_stats_prefix = (
            f"/api/trakaido/classrooms/{self.classroom_id}/members/{self.member.id}/stats/".encode()
        )
        self.assertIn(member_stats_prefix + b"lithuanian", response.data)
        self.assertIn(member_stats_prefix + b"chinese", response.data)
        # Manager (no stats dirs) should still show "No activity yet"
        self.assertIn(b"No activity yet", response.data)

    @patch("trakaido.blueprints.classroom_stats.calculate_monthly_progress")
    @patch("trakaido.blueprints.classroom_stats.calculate_weekly_progress")
    @patch("trakaido.blueprints.classroom_stats.calculate_daily_progress")
    @patch("trakaido.blueprints.classroom_stats.compute_member_summary")
    def test_daily_stats_page_renders_member_breakdown(
        self,
        mock_summary,
        mock_daily,
        mock_weekly,
        mock_monthly,
    ):
        mock_summary.return_value = {
            "wordsKnown": 11,
            "wordsExposed": 20,
            "wordsTracked": 30,
            "activitySummary": {
                "combined": {"totalAnswered": 8},
                "directPractice": {"totalAnswered": 5},
                "contextualExposure": {"totalAnswered": 3},
            },
        }
        mock_daily.return_value = {
            "currentDay": "2026-01-10",
            "progress": {
                "exposed": {"new": 2, "total": 20},
                "directPractice": {
                    "multipleChoice_englishToTarget": {"correct": 1, "incorrect": 0}
                },
                "contextualExposure": {"sentences": {"correct": 1, "incorrect": 1}},
            },
        }
        mock_weekly.return_value = {"progress": {"exposed": {"new": 1, "total": 20}}}
        mock_monthly.return_value = {"monthlyAggregate": {"exposed": {"new": 5, "total": 20}}}

        response = self.client.get(
            f"/api/trakaido/classrooms/{self.classroom_id}/stats/lithuanian/daily",
            headers=self._auth_headers("manager-token"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Daily classroom stats", response.data)
        self.assertIn(b"Per-member breakdown", response.data)
        self.assertIn(b"Manager", response.data)
        self.assertIn(b"Member", response.data)

    @patch("trakaido.blueprints.classroom_stats.calculate_monthly_progress")
    @patch("trakaido.blueprints.classroom_stats.calculate_weekly_progress")
    @patch("trakaido.blueprints.classroom_stats.calculate_daily_progress")
    @patch("trakaido.blueprints.classroom_stats.compute_member_summary")
    def test_stats_page_rejects_unknown_language(
        self,
        mock_summary,
        mock_daily,
        mock_weekly,
        mock_monthly,
    ):
        response = self.client.get(
            f"/api/trakaido/classrooms/{self.classroom_id}/stats/klingon/daily",
            headers=self._auth_headers("manager-token"),
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"Unknown language", response.data)

    def test_member_detail_requires_manager(self):
        response = self.client.get(
            f"/api/trakaido/classrooms/{self.classroom_id}/members/{self.member.id}/stats/lithuanian",
            headers=self._auth_headers("member-token"),
        )

        self.assertEqual(response.status_code, 403)
        self.assertIn(b"Manager access required", response.data)

    @patch("trakaido.blueprints.classroom_stats.get_journey_stats")
    @patch("trakaido.blueprints.classroom_stats.calculate_monthly_progress")
    @patch("trakaido.blueprints.classroom_stats.calculate_weekly_progress")
    @patch("trakaido.blueprints.classroom_stats.calculate_daily_progress")
    @patch("trakaido.blueprints.classroom_stats.compute_member_summary")
    def test_member_detail_shows_daily_chart_and_recent_words(
        self,
        mock_summary,
        mock_daily,
        mock_weekly,
        mock_monthly,
        mock_journey_stats,
    ):
        mock_summary.return_value = {
            "wordsKnown": 10,
            "wordsExposed": 18,
            "wordsTracked": 18,
            "activitySummary": {"combined": {"totalAnswered": 44}},
        }
        mock_daily.return_value = {
            "currentDay": "2026-01-10",
            "targetBaselineDay": "2026-01-09",
            "progress": {"exposed": {"new": 2, "total": 18}},
        }
        mock_weekly.return_value = {
            "currentDay": "2026-01-10",
            "actualBaselineDay": "2026-01-03",
            "progress": {"exposed": {"new": 4, "total": 18}},
        }
        mock_monthly.return_value = {
            "currentDay": "2026-01-10",
            "actualBaselineDay": "2025-12-11",
            "monthlyAggregate": {"exposed": {"new": 6, "total": 18}},
            "dailyData": [
                {"date": "2026-01-08", "questionsAnswered": 3},
                {"date": "2026-01-09", "questionsAnswered": 5},
                {"date": "2026-01-10", "questionsAnswered": 7},
            ],
        }

        mock_journey = mock_journey_stats.return_value
        mock_journey.stats = {
            "stats": {
                "labas": {
                    "practiceHistory": {"lastSeen": 1761000000},
                    "directPractice": {
                        "multipleChoice_englishToTarget": {"correct": 2, "incorrect": 1}
                    },
                },
                "rytas": {
                    "practiceHistory": {"lastSeen": 1760900000},
                    "contextualExposure": {"sentences": {"correct": 1, "incorrect": 0}},
                },
            }
        }

        response = self.client.get(
            f"/api/trakaido/classrooms/{self.classroom_id}/members/{self.member.id}/stats/lithuanian",
            headers=self._auth_headers("manager-token"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Questions answered per day (past 30 days)", response.data)
        self.assertIn(b"Ten most recent words", response.data)
        self.assertIn(b"labas", response.data)

    @patch("atacama.decorators.auth.get_user_config_manager")
    def test_admin_can_create_classroom_and_manage_members_by_email(self, mock_get_manager):
        mock_get_manager.return_value.is_admin.return_value = True
        self._set_admin_session()

        create_response = self._admin_post(
            "/api/trakaido/admin/classrooms",
            json={"name": "Evening Group", "managerEmail": self.manager.email},
        )
        self.assertEqual(create_response.status_code, 201)
        created_classroom_id = create_response.get_json()["classroom"]["id"]

        search_response = self._admin_get("/api/trakaido/admin/users/search?email=member@")
        self.assertEqual(search_response.status_code, 200)
        search_payload = search_response.get_json()
        self.assertGreaterEqual(search_payload["count"], 1)
        self.assertTrue(any(user["email"] == self.member.email for user in search_payload["users"]))

        add_response = self._admin_post(
            f"/api/trakaido/admin/classrooms/{created_classroom_id}/members",
            json={"email": self.member.email},
        )
        self.assertEqual(add_response.status_code, 201)
        self.assertEqual(add_response.get_json()["member"]["role"], ClassroomRole.MEMBER.value)

        promote_response = self._admin_post(
            f"/api/trakaido/admin/classrooms/{created_classroom_id}/members",
            json={"email": self.member.email, "role": "manager"},
        )
        self.assertEqual(promote_response.status_code, 200)
        self.assertEqual(promote_response.get_json()["member"]["role"], ClassroomRole.MANAGER.value)

        remove_response = self._admin_post(
            f"/api/trakaido/admin/classrooms/{created_classroom_id}/members/remove",
            json={"email": self.member.email},
        )
        self.assertEqual(remove_response.status_code, 200)
        self.assertEqual(remove_response.get_json()["removed"]["email"], self.member.email)

    @patch("atacama.decorators.auth.get_user_config_manager")
    def test_admin_cannot_remove_last_classroom_manager(self, mock_get_manager):
        mock_get_manager.return_value.is_admin.return_value = True
        self._set_admin_session()

        create_response = self._admin_post(
            "/api/trakaido/admin/classrooms",
            json={"name": "Solo Manager Group"},
        )
        created_classroom_id = create_response.get_json()["classroom"]["id"]

        remove_response = self._admin_post(
            f"/api/trakaido/admin/classrooms/{created_classroom_id}/members/remove",
            json={"email": self.admin.email},
        )
        self.assertEqual(remove_response.status_code, 400)
        self.assertIn("last classroom manager", remove_response.get_json()["error"])


if __name__ == "__main__":
    unittest.main()

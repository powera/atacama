"""Tests for classroom stats HTML routes."""

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
        constants.DATA_DIR = self.temp_dir

        self.app = create_app(testing=True, blueprint_set='TRAKAIDO')
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

        with db.session() as session:
            self.manager = User(email="manager@example.com", name="Manager")
            self.member = User(email="member@example.com", name="Member")
            self.outsider = User(email="outsider@example.com", name="Outsider")
            session.add_all([self.manager, self.member, self.outsider])
            session.flush()

            session.add_all([
                UserToken(user_id=self.manager.id, token="manager-token"),
                UserToken(user_id=self.member.id, token="member-token"),
                UserToken(user_id=self.outsider.id, token="outsider-token"),
            ])

            classroom = Classroom(name="A1 Lithuanian", created_by_user_id=self.manager.id)
            session.add(classroom)
            session.flush()
            self.classroom_id = classroom.id

            session.add_all([
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
            ])

    def tearDown(self):
        db.cleanup()
        self.app_context.pop()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        constants.DATA_DIR = self.original_data_dir

    def _auth_headers(self, token: str):
        return {"Authorization": f"Bearer {token}"}

    def test_classrooms_page_renders_for_authenticated_user(self):
        response = self.client.get('/api/trakaido/classrooms/', headers=self._auth_headers("manager-token"))

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'My Classrooms', response.data)
        self.assertIn(b'A1 Lithuanian', response.data)

    def test_members_page_requires_manager_role(self):
        response = self.client.get(
            f'/api/trakaido/classrooms/{self.classroom_id}/members',
            headers=self._auth_headers("member-token"),
        )

        self.assertEqual(response.status_code, 403)
        self.assertIn(b'Manager access required', response.data)

    @patch('trakaido.blueprints.classroom_stats.calculate_monthly_progress')
    @patch('trakaido.blueprints.classroom_stats.calculate_weekly_progress')
    @patch('trakaido.blueprints.classroom_stats.calculate_daily_progress')
    @patch('trakaido.blueprints.classroom_stats.compute_member_summary')
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
                "contextualExposure": {
                    "sentences": {"correct": 1, "incorrect": 1}
                },
            },
        }
        mock_weekly.return_value = {"progress": {"exposed": {"new": 1, "total": 20}}}
        mock_monthly.return_value = {"monthlyAggregate": {"exposed": {"new": 5, "total": 20}}}

        response = self.client.get(
            f'/api/trakaido/classrooms/{self.classroom_id}/stats/daily',
            headers=self._auth_headers("manager-token"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Daily classroom stats', response.data)
        self.assertIn(b'Per-member breakdown', response.data)
        self.assertIn(b'Manager', response.data)
        self.assertIn(b'Member', response.data)

    def test_member_detail_requires_manager(self):
        response = self.client.get(
            f'/api/trakaido/classrooms/{self.classroom_id}/members/{self.member.id}/stats',
            headers=self._auth_headers("member-token"),
        )

        self.assertEqual(response.status_code, 403)
        self.assertIn(b'Manager access required', response.data)


if __name__ == '__main__':
    unittest.main()

"""Tests for classroom model helpers."""

import unittest

import constants
from models.database import db
from models.classrooms import (
    get_class_members,
    get_user_classroom_capabilities,
    get_user_classrooms,
    is_class_manager,
)
from models.models import User


class TestClassroomHelpers(unittest.TestCase):
    def setUp(self):
        constants.init_testing(test_db_path="sqlite:///:memory:", service="trakaido")
        db.cleanup()
        self.assertTrue(db.initialize())

        from trakaido.models import Classroom, ClassroomMembership, ClassroomRole

        self.Classroom = Classroom
        self.ClassroomMembership = ClassroomMembership
        self.ClassroomRole = ClassroomRole

        with db.session() as db_session:
            manager = User(email="manager@example.com", name="Manager")
            member = User(email="member@example.com", name="Member")
            db_session.add_all([manager, member])
            db_session.flush()

            classroom = Classroom(
                name="Lithuanian A1", created_by_user_id=manager.id, archived=False
            )
            db_session.add(classroom)
            db_session.flush()

            db_session.add_all(
                [
                    ClassroomMembership(
                        classroom_id=classroom.id,
                        user_id=manager.id,
                        role=ClassroomRole.MANAGER,
                    ),
                    ClassroomMembership(
                        classroom_id=classroom.id,
                        user_id=member.id,
                        role=ClassroomRole.MEMBER,
                    ),
                ]
            )

            self.manager_id = manager.id
            self.member_id = member.id
            self.classroom_id = classroom.id

    def tearDown(self):
        db.cleanup()
        constants.reset()

    def test_is_class_manager(self):
        self.assertTrue(is_class_manager(self.manager_id, self.classroom_id))
        self.assertFalse(is_class_manager(self.member_id, self.classroom_id))

    def test_get_user_classrooms(self):
        classrooms = get_user_classrooms(self.member_id)
        self.assertEqual(len(classrooms), 1)
        self.assertEqual(classrooms[0].name, "Lithuanian A1")


    def test_get_user_classroom_capabilities(self):
        capabilities = get_user_classroom_capabilities(self.manager_id)

        self.assertTrue(capabilities["is_class_manager"])
        self.assertEqual(len(capabilities["managed_classrooms"]), 1)
        self.assertEqual(capabilities["managed_classrooms"][0]["id"], self.classroom_id)
        self.assertEqual(capabilities["managed_classrooms"][0]["display_name"], "Lithuanian A1")
        self.assertEqual(capabilities["managed_classrooms"][0]["member_count"], 2)
        self.assertEqual(capabilities["member_classrooms"], [])

    def test_get_class_members(self):
        memberships = get_class_members(self.classroom_id)
        self.assertEqual(len(memberships), 2)
        self.assertEqual(memberships[0].role, self.ClassroomRole.MANAGER)
        self.assertEqual(memberships[1].role, self.ClassroomRole.MEMBER)


class TestClassroomHelpersDisabledService(unittest.TestCase):
    def setUp(self):
        constants.init_testing(test_db_path="sqlite:///:memory:", service="blog")
        db.cleanup()

    def tearDown(self):
        db.cleanup()
        constants.reset()

    def test_helpers_noop_when_trakaido_disabled(self):
        self.assertFalse(is_class_manager(1, 1))
        self.assertEqual(get_user_classrooms(1), [])
        self.assertEqual(get_class_members(1), [])
        self.assertEqual(
            get_user_classroom_capabilities(1),
            {
                "is_class_manager": False,
                "managed_classrooms": [],
                "member_classrooms": [],
            },
        )


if __name__ == "__main__":
    unittest.main()

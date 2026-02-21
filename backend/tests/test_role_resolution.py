import unittest

from app.core.security import _resolve_role


class TestRoleResolution(unittest.TestCase):
    def test_admin_email_always_wins(self):
        self.assertEqual(_resolve_role(email_is_admin=True, db_role="user"), "admin")

    def test_admin_email_wins_over_no_db_role(self):
        self.assertEqual(_resolve_role(email_is_admin=True, db_role=None), "admin")

    def test_db_admin_without_email(self):
        self.assertEqual(_resolve_role(email_is_admin=False, db_role="admin"), "admin")

    def test_db_role_non_admin(self):
        self.assertEqual(_resolve_role(email_is_admin=False, db_role="support"), "support")

    def test_default_user(self):
        self.assertEqual(_resolve_role(email_is_admin=False, db_role=None), "user")


if __name__ == "__main__":
    unittest.main()

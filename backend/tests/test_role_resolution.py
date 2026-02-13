import unittest


from app.core.security import _decide_role


class TestRoleResolution(unittest.TestCase):
    def test_db_admin_wins(self):
        role, reason = _decide_role(email_is_admin=False, claim_is_admin=False, db_role="admin", supabase_role="user")
        self.assertEqual(role, "admin")
        self.assertEqual(reason, "db_profile")

    def test_admin_emails(self):
        role, reason = _decide_role(email_is_admin=True, claim_is_admin=False, db_role="user", supabase_role=None)
        self.assertEqual(role, "admin")
        self.assertEqual(reason, "admin_emails")

    def test_jwt_claim(self):
        role, reason = _decide_role(email_is_admin=False, claim_is_admin=True, db_role="user", supabase_role=None)
        self.assertEqual(role, "admin")
        self.assertEqual(reason, "jwt_claim")

    def test_supabase_profiles_admin(self):
        role, reason = _decide_role(email_is_admin=False, claim_is_admin=False, db_role="user", supabase_role="admin")
        self.assertEqual(role, "admin")
        self.assertEqual(reason, "supabase_profiles")

    def test_db_role_non_admin(self):
        role, reason = _decide_role(email_is_admin=False, claim_is_admin=False, db_role="support", supabase_role=None)
        self.assertEqual(role, "support")
        self.assertEqual(reason, "db_profile")

    def test_default_user(self):
        role, reason = _decide_role(email_is_admin=False, claim_is_admin=False, db_role=None, supabase_role=None)
        self.assertEqual(role, "user")
        self.assertEqual(reason, "default")


if __name__ == "__main__":
    unittest.main()


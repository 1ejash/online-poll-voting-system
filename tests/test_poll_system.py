import os
import unittest
from werkzeug.security import check_password_hash

from app import create_app
from config import TestConfig
from db import db
from auth_utils import is_valid_gmail, validate_password


class TestGmailValidation(unittest.TestCase):
    """Test suite validating strict @gmail.com enforcement."""

    def test_valid_standard_gmail(self):
        valid, msg = is_valid_gmail("john.doe2026@gmail.com")
        self.assertTrue(valid)
        self.assertEqual(msg, "")

    def test_valid_alphanumeric_gmail(self):
        valid, _ = is_valid_gmail("voter12345@gmail.com")
        self.assertTrue(valid)

    def test_case_insensitivity(self):
        valid, _ = is_valid_gmail("VOTER.TEST@GMAIL.COM")
        self.assertTrue(valid)

    def test_reject_non_gmail_domains(self):
        invalid_domains = [
            "user@yahoo.com",
            "user@outlook.com",
            "user@hotmail.com",
            "user@company.org",
            "user@tempmail.net",
            "user@protonmail.com",
            "user@gmail.org",
            "user@gmail.co"
        ]
        for email in invalid_domains:
            valid, msg = is_valid_gmail(email)
            self.assertFalse(valid, f"Should reject domain for {email}")
            self.assertIn("Only genuine @gmail.com", msg)

    def test_reject_short_username(self):
                                                          
        valid, msg = is_valid_gmail("abcde@gmail.com")
        self.assertFalse(valid)
        self.assertIn("at least 6 characters", msg)

    def test_reject_consecutive_dots(self):
        valid, msg = is_valid_gmail("john..doe@gmail.com")
        self.assertFalse(valid)
        self.assertIn("consecutive periods", msg)

    def test_reject_leading_trailing_dots(self):
        valid1, _ = is_valid_gmail(".johndoe@gmail.com")
        self.assertFalse(valid1)
        valid2, _ = is_valid_gmail("johndoe.@gmail.com")
        self.assertFalse(valid2)

    def test_reject_special_characters(self):
        valid, _ = is_valid_gmail("john#doe@gmail.com")
        self.assertFalse(valid)
        valid2, _ = is_valid_gmail("john$doe@gmail.com")
        self.assertFalse(valid2)

    def test_empty_or_none_email(self):
        valid1, _ = is_valid_gmail("")
        self.assertFalse(valid1)
        valid2, _ = is_valid_gmail(None)
        self.assertFalse(valid2)


class BaseTestCase(unittest.TestCase):
    """Base setup for Flask application testing."""

    def setUp(self):
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

    def tearDown(self):
        self.app_context.pop()

    def register_user(self, name="Test Voter", email="test.voter@gmail.com", password="Password123"):
        return self.client.post("/register", data={
            "name": name,
            "email": email,
            "password": password,
            "confirm_password": password
        }, follow_redirects=True)

    def login_user(self, email="test.voter@gmail.com", password="Password123"):
        return self.client.post("/user-login", data={
            "email": email,
            "password": password
        }, follow_redirects=True)

    def login_admin(self, email="admin@gmail.com", password="Admin@123"):
        return self.client.post("/admin-login", data={
            "email": email,
            "password": password
        }, follow_redirects=True)


class TestUserRegistrationAndAuth(BaseTestCase):
    """Test user registration, duplicate checks, and authentication."""

    def test_successful_registration(self):
        res = self.register_user("Alice Smith", "alice.smith42@gmail.com", "Secret123")
        self.assertEqual(res.status_code, 200)

                                                                  
        user = db.fetchone("SELECT * FROM users WHERE email = %s", ("alice.smith42@gmail.com",))
        self.assertIsNotNone(user)
        self.assertEqual(user["name"], "Alice Smith")
        self.assertTrue(check_password_hash(user["password"], "Secret123"))

    def test_reject_registration_non_gmail(self):
        res = self.register_user("Bob Jones", "bob.jones@yahoo.com", "Secret123")
        self.assertEqual(res.status_code, 200)
        user = db.fetchone("SELECT * FROM users WHERE email = %s", ("bob.jones@yahoo.com",))
        self.assertIsNone(user)

    def test_duplicate_registration_rejected(self):
        self.register_user("Carol Danvers", "carol.danvers@gmail.com", "Secret123")
                                               
        res = self.register_user("Carol Danvers", "carol.danvers@gmail.com", "Secret123")
        self.assertEqual(res.status_code, 200)
                                     
        users = db.fetchall("SELECT * FROM users WHERE email = %s", ("carol.danvers@gmail.com",))
        self.assertEqual(len(users), 1)

    def test_user_login_success_and_logout(self):
        self.register_user("David Miller", "david.miller@gmail.com", "Password123")
                
        self.client.get("/logout")

               
        res = self.login_user("david.miller@gmail.com", "Password123")
        self.assertEqual(res.status_code, 200)
        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get("user_email"), "david.miller@gmail.com")
            self.assertEqual(sess.get("user_role"), "user")

                
        logout_res = self.client.get("/logout", follow_redirects=True)
        self.assertEqual(logout_res.status_code, 200)
        with self.client.session_transaction() as sess:
            self.assertIsNone(sess.get("user_id"))

    def test_user_login_invalid_password(self):
        self.register_user("Eva Green", "eva.green@gmail.com", "Password123")
        self.client.get("/logout")

        res = self.login_user("eva.green@gmail.com", "WrongPassword")
        self.assertEqual(res.status_code, 200)
        with self.client.session_transaction() as sess:
            self.assertIsNone(sess.get("user_id"))


class TestRoleBasedAccessControl(BaseTestCase):
    """Test RBAC security constraints."""

    def test_unauthenticated_cannot_access_polls(self):
        res = self.client.get("/polls")
        self.assertEqual(res.status_code, 302)
        self.assertIn("/user-login", res.headers["Location"])

    def test_unauthenticated_cannot_access_admin(self):
        res = self.client.get("/admin")
        self.assertEqual(res.status_code, 302)
        self.assertIn("/admin-login", res.headers["Location"])

    def test_regular_user_cannot_access_admin(self):
        self.register_user("Regular User", "regular.user@gmail.com", "Password123")
        res = self.client.get("/admin", follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn("/polls", res.headers["Location"])

    def test_admin_can_access_admin_dashboard(self):
        res = self.login_admin()
        self.assertEqual(res.status_code, 200)
        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get("user_role"), "admin")


class TestVotingSystem(BaseTestCase):
    """Test poll creation, dynamic options, voting, and double-vote prevention."""

    def setUp(self):
        super().setUp()
                                  
        poll_id = db.execute(
            "INSERT INTO polls (question, description, status) VALUES (%s, %s, 'active')",
            ("What is your favorite language?", "Programming language preferences")
        )
        self.poll_id = poll_id
        self.opt1 = db.execute("INSERT INTO poll_options (poll_id, option_text) VALUES (%s, %s)", (poll_id, "Python"))
        self.opt2 = db.execute("INSERT INTO poll_options (poll_id, option_text) VALUES (%s, %s)", (poll_id, "JavaScript"))

    def test_single_vote_successful(self):
        self.register_user("Voter One", "voter.one@gmail.com", "Password123")
        res = self.client.post(f"/vote/{self.poll_id}", data={"option_id": self.opt1}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

                             
        vote = db.fetchone("SELECT * FROM votes WHERE poll_id = %s", (self.poll_id,))
        self.assertIsNotNone(vote)
        self.assertEqual(vote["option_id"], self.opt1)

    def test_double_vote_prevented(self):
        self.register_user("Voter Two", "voter.two@gmail.com", "Password123")
                    
        self.client.post(f"/vote/{self.poll_id}", data={"option_id": self.opt1}, follow_redirects=True)

                             
        res = self.client.post(f"/vote/{self.poll_id}", data={"option_id": self.opt2}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

                                                       
        votes = db.fetchall("SELECT * FROM votes WHERE poll_id = %s", (self.poll_id,))
        self.assertEqual(len(votes), 1)

    def test_voting_on_closed_poll_rejected(self):
        db.execute("UPDATE polls SET status = 'closed' WHERE id = %s", (self.poll_id,))
        self.register_user("Voter Three", "voter.three@gmail.com", "Password123")

        res = self.client.post(f"/vote/{self.poll_id}", data={"option_id": self.opt1}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        votes = db.fetchall("SELECT * FROM votes WHERE poll_id = %s", (self.poll_id,))
        self.assertEqual(len(votes), 0)


class TestAdminPollManagement(BaseTestCase):
    """Test admin creating, updating, toggling, and deleting polls."""

    def setUp(self):
        super().setUp()
        self.login_admin()

    def test_create_poll_with_dynamic_options(self):
        res = self.client.post("/admin/create-poll", data={
            "question": "Which database engine?",
            "description": "SQL preference",
            "option1": "MySQL",
            "option2": "PostgreSQL",
            "option3": "SQLite"
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        poll = db.fetchone("SELECT * FROM polls WHERE question = %s", ("Which database engine?",))
        self.assertIsNotNone(poll)
        options = db.fetchall("SELECT * FROM poll_options WHERE poll_id = %s", (poll["id"],))
        self.assertEqual(len(options), 3)

    def test_toggle_poll_status(self):
        poll_id = db.execute("INSERT INTO polls (question, status) VALUES (%s, 'active')", ("Toggle Test Poll",))
                          
        self.client.post(f"/admin/toggle-poll/{poll_id}", follow_redirects=True)
        poll = db.fetchone("SELECT status FROM polls WHERE id = %s", (poll_id,))
        self.assertEqual(poll["status"], "closed")

                               
        self.client.post(f"/admin/toggle-poll/{poll_id}", follow_redirects=True)
        poll = db.fetchone("SELECT status FROM polls WHERE id = %s", (poll_id,))
        self.assertEqual(poll["status"], "active")

    def test_delete_poll_cascade(self):
        poll_id = db.execute("INSERT INTO polls (question, status) VALUES (%s, 'active')", ("Delete Me Poll",))
        opt_id = db.execute("INSERT INTO poll_options (poll_id, option_text) VALUES (%s, 'Opt')", (poll_id,))

        self.client.post(f"/admin/delete-poll/{poll_id}", follow_redirects=True)
        self.assertIsNone(db.fetchone("SELECT * FROM polls WHERE id = %s", (poll_id,)))
        self.assertEqual(len(db.fetchall("SELECT * FROM poll_options WHERE poll_id = %s", (poll_id,))), 0)

    def test_voter_audit_log_access(self):
        res = self.client.get("/admin/voters")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Voter Audit Log", res.data)


class TestSecurityHeaders(BaseTestCase):
    """Test security response headers."""

    def test_security_headers_present(self):
        res = self.client.get("/")
        self.assertEqual(res.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(res.headers.get("X-Frame-Options"), "SAMEORIGIN")
        self.assertEqual(res.headers.get("X-XSS-Protection"), "1; mode=block")
        self.assertEqual(res.headers.get("Referrer-Policy"), "strict-origin-when-cross-origin")


if __name__ == "__main__":
    unittest.main()

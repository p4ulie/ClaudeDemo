"""Integration tests for Flask routes and JSON API endpoints.
Uses a temporary data file for isolation from real application data."""

import os
import tempfile
import unittest
from pathlib import Path

import models
from app import create_app


class RouteTestCase(unittest.TestCase):
    """Base class that sets up a Flask test client with an isolated temp data file."""

    def setUp(self):
        # Create a temporary JSON file to isolate test data
        self.tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        )
        self.tmp.close()
        # Redirect the models module to use the temp file
        self._orig = models.DATA_FILE
        models.DATA_FILE = Path(self.tmp.name)
        # Create the Flask app in testing mode with a test client
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def tearDown(self):
        # Restore original data file path and clean up
        models.DATA_FILE = self._orig
        if os.path.exists(self.tmp.name):
            os.unlink(self.tmp.name)


class TestIndex(RouteTestCase):
    """Tests for the home page (skill list)."""

    def test_empty_index(self):
        """Home page should show empty state message when no skills exist."""
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"No skills yet", resp.data)

    def test_index_with_skill(self):
        """Home page should display a skill after it's been created."""
        models.create_skill("Rust", 7200)
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Rust", resp.data)


class TestCreateSkill(RouteTestCase):
    """Tests for the skill creation form submission."""

    def test_create_valid(self):
        """A valid form submission should create a skill and show it on the page."""
        resp = self.client.post("/skills", data={
            "name": "Piano", "hours": "1", "minutes": "30"
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Piano", resp.data)
        self.assertEqual(len(models.load_skills()), 1)

    def test_create_empty_name(self):
        """Submitting an empty name should not create a skill."""
        resp = self.client.post("/skills", data={
            "name": "", "hours": "1", "minutes": "0"
        }, follow_redirects=True)
        self.assertEqual(len(models.load_skills()), 0)

    def test_create_zero_time(self):
        """Submitting zero hours and zero minutes should not create a skill."""
        resp = self.client.post("/skills", data={
            "name": "X", "hours": "0", "minutes": "0"
        }, follow_redirects=True)
        self.assertEqual(len(models.load_skills()), 0)


class TestTimerRoutes(RouteTestCase):
    """Tests for the HTML timer start/stop routes."""

    def test_start_stop(self):
        """Starting and stopping a timer via HTML routes should record a session."""
        skill = models.create_skill("Go", 3600)
        # Start the timer
        self.client.post(f"/skills/{skill.id}/start")
        updated = models.get_skill(skill.id)
        self.assertIsNotNone(updated.active_since)

        # Stop the timer
        self.client.post(f"/skills/{skill.id}/stop")
        updated = models.get_skill(skill.id)
        self.assertIsNone(updated.active_since)
        self.assertEqual(len(updated.sessions), 1)


class TestDeleteRoute(RouteTestCase):
    """Tests for the skill deletion route."""

    def test_delete(self):
        """Deleting a skill should remove it from storage."""
        skill = models.create_skill("Go", 3600)
        resp = self.client.post(f"/skills/{skill.id}/delete", follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(models.load_skills()), 0)


class TestLogRoute(RouteTestCase):
    """Tests for the session log page."""

    def test_log_page(self):
        """Log page should render successfully and show the skill name."""
        skill = models.create_skill("Go", 3600)
        resp = self.client.get(f"/skills/{skill.id}/log")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Go", resp.data)

    def test_log_nonexistent(self):
        """Requesting a log for a non-existent skill should redirect to home."""
        resp = self.client.get("/skills/nope/log")
        self.assertEqual(resp.status_code, 302)


class TestAPI(RouteTestCase):
    """Tests for the JSON API endpoints used by timer.js."""

    def test_api_start_stop(self):
        """API start/stop should return JSON with timer state and session data."""
        skill = models.create_skill("Rust", 7200)
        # Start via API
        resp = self.client.post(f"/api/skills/{skill.id}/start")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("active_since", data)

        # Stop via API
        resp = self.client.post(f"/api/skills/{skill.id}/stop")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("duration_seconds", data)

    def test_api_skill(self):
        """API skill endpoint should return skill details with remaining time."""
        skill = models.create_skill("Rust", 7200)
        resp = self.client.get(f"/api/skills/{skill.id}")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["name"], "Rust")
        self.assertEqual(data["remaining_seconds"], 7200)

    def test_api_not_found(self):
        """API should return 404 for a non-existent skill."""
        resp = self.client.post("/api/skills/nope/start")
        self.assertEqual(resp.status_code, 404)


if __name__ == "__main__":
    unittest.main()

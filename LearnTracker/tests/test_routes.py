"""Integration tests for Flask routes."""

import os
import tempfile
import unittest
from pathlib import Path

import models
from app import create_app


class RouteTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        )
        self.tmp.close()
        self._orig = models.DATA_FILE
        models.DATA_FILE = Path(self.tmp.name)
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def tearDown(self):
        models.DATA_FILE = self._orig
        if os.path.exists(self.tmp.name):
            os.unlink(self.tmp.name)


class TestIndex(RouteTestCase):
    def test_empty_index(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"No skills yet", resp.data)

    def test_index_with_skill(self):
        models.create_skill("Rust", 7200)
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Rust", resp.data)


class TestCreateSkill(RouteTestCase):
    def test_create_valid(self):
        resp = self.client.post("/skills", data={
            "name": "Piano", "hours": "1", "minutes": "30"
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Piano", resp.data)
        self.assertEqual(len(models.load_skills()), 1)

    def test_create_empty_name(self):
        resp = self.client.post("/skills", data={
            "name": "", "hours": "1", "minutes": "0"
        }, follow_redirects=True)
        self.assertEqual(len(models.load_skills()), 0)

    def test_create_zero_time(self):
        resp = self.client.post("/skills", data={
            "name": "X", "hours": "0", "minutes": "0"
        }, follow_redirects=True)
        self.assertEqual(len(models.load_skills()), 0)


class TestTimerRoutes(RouteTestCase):
    def test_start_stop(self):
        skill = models.create_skill("Go", 3600)
        self.client.post(f"/skills/{skill.id}/start")
        updated = models.get_skill(skill.id)
        self.assertIsNotNone(updated.active_since)

        self.client.post(f"/skills/{skill.id}/stop")
        updated = models.get_skill(skill.id)
        self.assertIsNone(updated.active_since)
        self.assertEqual(len(updated.sessions), 1)


class TestDeleteRoute(RouteTestCase):
    def test_delete(self):
        skill = models.create_skill("Go", 3600)
        resp = self.client.post(f"/skills/{skill.id}/delete", follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(models.load_skills()), 0)


class TestLogRoute(RouteTestCase):
    def test_log_page(self):
        skill = models.create_skill("Go", 3600)
        resp = self.client.get(f"/skills/{skill.id}/log")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Go", resp.data)

    def test_log_nonexistent(self):
        resp = self.client.get("/skills/nope/log")
        self.assertEqual(resp.status_code, 302)


class TestAPI(RouteTestCase):
    def test_api_start_stop(self):
        skill = models.create_skill("Rust", 7200)
        resp = self.client.post(f"/api/skills/{skill.id}/start")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("active_since", data)

        resp = self.client.post(f"/api/skills/{skill.id}/stop")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("duration_seconds", data)

    def test_api_skill(self):
        skill = models.create_skill("Rust", 7200)
        resp = self.client.get(f"/api/skills/{skill.id}")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["name"], "Rust")
        self.assertEqual(data["remaining_seconds"], 7200)

    def test_api_not_found(self):
        resp = self.client.post("/api/skills/nope/start")
        self.assertEqual(resp.status_code, 404)


if __name__ == "__main__":
    unittest.main()

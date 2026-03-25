"""Unit tests for the data layer."""

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import models


class ModelTestCase(unittest.TestCase):
    """Base class that redirects DATA_FILE to a temp file."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        )
        self.tmp.close()
        self._orig = models.DATA_FILE
        models.DATA_FILE = Path(self.tmp.name)

    def tearDown(self):
        models.DATA_FILE = self._orig
        if os.path.exists(self.tmp.name):
            os.unlink(self.tmp.name)


class TestLoadSave(ModelTestCase):
    def test_empty_load(self):
        os.unlink(self.tmp.name)  # file doesn't exist yet
        skills = models.load_skills()
        self.assertEqual(skills, [])

    def test_round_trip(self):
        skill = models.create_skill("Rust", 7200)
        loaded = models.load_skills()
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].name, "Rust")
        self.assertEqual(loaded[0].target_seconds, 7200)


class TestCreateDelete(ModelTestCase):
    def test_create_skill(self):
        skill = models.create_skill("Piano", 3600)
        self.assertEqual(skill.name, "Piano")
        self.assertEqual(skill.target_seconds, 3600)
        self.assertEqual(len(skill.id), 6)
        self.assertEqual(skill.sessions, [])

    def test_delete_skill(self):
        skill = models.create_skill("Piano", 3600)
        self.assertTrue(models.delete_skill(skill.id))
        self.assertEqual(models.load_skills(), [])

    def test_delete_nonexistent(self):
        self.assertFalse(models.delete_skill("nope"))

    def test_get_skill(self):
        skill = models.create_skill("Go", 1800)
        found = models.get_skill(skill.id)
        self.assertIsNotNone(found)
        self.assertEqual(found.name, "Go")

    def test_get_skill_not_found(self):
        self.assertIsNone(models.get_skill("nope"))


class TestTimer(ModelTestCase):
    def test_start_stop(self):
        skill = models.create_skill("Rust", 7200)
        started = models.start_timer(skill.id)
        self.assertIsNotNone(started.active_since)

        session = models.stop_timer(skill.id)
        self.assertIsNotNone(session)
        self.assertGreaterEqual(session.duration_seconds, 0)

        updated = models.get_skill(skill.id)
        self.assertIsNone(updated.active_since)
        self.assertEqual(len(updated.sessions), 1)

    def test_start_already_running(self):
        skill = models.create_skill("Rust", 7200)
        models.start_timer(skill.id)
        again = models.start_timer(skill.id)
        self.assertIsNotNone(again.active_since)

    def test_stop_not_running(self):
        skill = models.create_skill("Rust", 7200)
        self.assertIsNone(models.stop_timer(skill.id))

    def test_stop_nonexistent(self):
        self.assertIsNone(models.stop_timer("nope"))

    def test_start_nonexistent(self):
        self.assertIsNone(models.start_timer("nope"))


class TestComputed(ModelTestCase):
    def test_elapsed_and_remaining(self):
        skill = models.create_skill("Rust", 7200)
        # Manually add a session
        skills = models.load_skills()
        skills[0].sessions.append(
            models.Session(
                start="2026-03-25T10:00:00",
                end="2026-03-25T10:30:00",
                duration_seconds=1800,
            )
        )
        models.save_skills(skills)

        updated = models.get_skill(skill.id)
        self.assertEqual(models.elapsed_seconds(updated), 1800)
        self.assertEqual(models.remaining_seconds(updated), 5400)

    def test_remaining_never_negative(self):
        skill = models.create_skill("Rust", 60)
        skills = models.load_skills()
        skills[0].sessions.append(
            models.Session(
                start="2026-03-25T10:00:00",
                end="2026-03-25T11:00:00",
                duration_seconds=3600,
            )
        )
        models.save_skills(skills)

        updated = models.get_skill(skill.id)
        self.assertEqual(models.remaining_seconds(updated), 0)


class TestFormatDuration(unittest.TestCase):
    def test_seconds_only(self):
        self.assertEqual(models.format_duration(45), "45s")

    def test_minutes_and_seconds(self):
        self.assertEqual(models.format_duration(90), "1m 30s")

    def test_hours_minutes_seconds(self):
        self.assertEqual(models.format_duration(3661), "1h 01m 01s")

    def test_exact_hours(self):
        self.assertEqual(models.format_duration(7200), "2h 00m 00s")

    def test_zero(self):
        self.assertEqual(models.format_duration(0), "00s")


if __name__ == "__main__":
    unittest.main()

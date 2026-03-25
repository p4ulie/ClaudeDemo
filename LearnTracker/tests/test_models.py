"""Unit tests for the data layer (models.py).
Tests cover CRUD operations, timer logic, computed values, and duration formatting."""

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import models


class ModelTestCase(unittest.TestCase):
    """Base class that redirects DATA_FILE to a temp file for test isolation."""

    def setUp(self):
        # Create a temporary JSON file to avoid touching the real data.json
        self.tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        )
        self.tmp.close()
        # Swap the module-level DATA_FILE to the temp path
        self._orig = models.DATA_FILE
        models.DATA_FILE = Path(self.tmp.name)

    def tearDown(self):
        # Restore the original DATA_FILE path and clean up the temp file
        models.DATA_FILE = self._orig
        if os.path.exists(self.tmp.name):
            os.unlink(self.tmp.name)


class TestLoadSave(ModelTestCase):
    """Tests for reading and writing skills to the JSON data file."""

    def test_empty_load(self):
        """Loading from a missing file should return an empty list."""
        os.unlink(self.tmp.name)  # Simulate file not existing
        skills = models.load_skills()
        self.assertEqual(skills, [])

    def test_round_trip(self):
        """A skill created and saved should be fully recoverable on reload."""
        skill = models.create_skill("Rust", 7200)
        loaded = models.load_skills()
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].name, "Rust")
        self.assertEqual(loaded[0].target_seconds, 7200)


class TestCreateDelete(ModelTestCase):
    """Tests for creating, retrieving, and deleting skills."""

    def test_create_skill(self):
        """New skill should have correct fields and an empty session list."""
        skill = models.create_skill("Piano", 3600)
        self.assertEqual(skill.name, "Piano")
        self.assertEqual(skill.target_seconds, 3600)
        self.assertEqual(len(skill.id), 6)  # Short hex ID
        self.assertEqual(skill.sessions, [])

    def test_delete_skill(self):
        """Deleting an existing skill should remove it from storage."""
        skill = models.create_skill("Piano", 3600)
        self.assertTrue(models.delete_skill(skill.id))
        self.assertEqual(models.load_skills(), [])

    def test_delete_nonexistent(self):
        """Deleting a non-existent skill should return False."""
        self.assertFalse(models.delete_skill("nope"))

    def test_get_skill(self):
        """get_skill should find a skill by its ID."""
        skill = models.create_skill("Go", 1800)
        found = models.get_skill(skill.id)
        self.assertIsNotNone(found)
        self.assertEqual(found.name, "Go")

    def test_get_skill_not_found(self):
        """get_skill should return None for a non-existent ID."""
        self.assertIsNone(models.get_skill("nope"))


class TestTimer(ModelTestCase):
    """Tests for starting and stopping the countdown timer."""

    def test_start_stop(self):
        """Starting then stopping a timer should create one session."""
        skill = models.create_skill("Rust", 7200)
        # Start the timer — should set active_since
        started = models.start_timer(skill.id)
        self.assertIsNotNone(started.active_since)

        # Stop the timer — should return a session and clear active_since
        session = models.stop_timer(skill.id)
        self.assertIsNotNone(session)
        self.assertGreaterEqual(session.duration_seconds, 0)

        # Verify the skill state after stopping
        updated = models.get_skill(skill.id)
        self.assertIsNone(updated.active_since)
        self.assertEqual(len(updated.sessions), 1)

    def test_start_already_running(self):
        """Starting a timer that's already running should not reset it."""
        skill = models.create_skill("Rust", 7200)
        models.start_timer(skill.id)
        again = models.start_timer(skill.id)
        self.assertIsNotNone(again.active_since)

    def test_stop_not_running(self):
        """Stopping a timer that isn't running should return None."""
        skill = models.create_skill("Rust", 7200)
        self.assertIsNone(models.stop_timer(skill.id))

    def test_stop_nonexistent(self):
        """Stopping a timer for a non-existent skill should return None."""
        self.assertIsNone(models.stop_timer("nope"))

    def test_start_nonexistent(self):
        """Starting a timer for a non-existent skill should return None."""
        self.assertIsNone(models.start_timer("nope"))


class TestComputed(ModelTestCase):
    """Tests for elapsed_seconds and remaining_seconds computations."""

    def test_elapsed_and_remaining(self):
        """Elapsed and remaining should correctly reflect logged sessions."""
        skill = models.create_skill("Rust", 7200)
        # Manually inject a 30-minute session
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
        self.assertEqual(models.elapsed_seconds(updated), 1800)    # 30 minutes logged
        self.assertEqual(models.remaining_seconds(updated), 5400)  # 1h30m remaining

    def test_remaining_never_negative(self):
        """Remaining seconds should never go below zero, even if sessions exceed target."""
        skill = models.create_skill("Rust", 60)  # 1-minute target
        # Inject a session that far exceeds the target
        skills = models.load_skills()
        skills[0].sessions.append(
            models.Session(
                start="2026-03-25T10:00:00",
                end="2026-03-25T11:00:00",
                duration_seconds=3600,  # 1 hour — way over the 1-minute target
            )
        )
        models.save_skills(skills)

        updated = models.get_skill(skill.id)
        self.assertEqual(models.remaining_seconds(updated), 0)  # Clamped to zero


class TestFormatDuration(unittest.TestCase):
    """Tests for the human-readable duration formatter."""

    def test_seconds_only(self):
        """Durations under a minute should show only seconds."""
        self.assertEqual(models.format_duration(45), "45s")

    def test_minutes_and_seconds(self):
        """Durations under an hour should show minutes and seconds."""
        self.assertEqual(models.format_duration(90), "1m 30s")

    def test_hours_minutes_seconds(self):
        """Durations over an hour should show all three components."""
        self.assertEqual(models.format_duration(3661), "1h 01m 01s")

    def test_exact_hours(self):
        """Exact hour values should show zero minutes and seconds."""
        self.assertEqual(models.format_duration(7200), "2h 00m 00s")

    def test_zero(self):
        """Zero seconds should display as '00s'."""
        self.assertEqual(models.format_duration(0), "00s")


if __name__ == "__main__":
    unittest.main()

"""Data layer for LearnTracker — Skill/Session dataclasses and JSON persistence."""

import json
import os
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path

# Path to the JSON file that stores all skill and session data
DATA_FILE = Path(__file__).parent / "data.json"


@dataclass
class Session:
    """Represents a single timed learning session with start/end timestamps."""
    start: str            # ISO 8601 timestamp when the session began
    end: str              # ISO 8601 timestamp when the session ended
    duration_seconds: int  # Total seconds spent in this session


@dataclass
class Skill:
    """Represents a learning skill with a time budget and recorded sessions."""
    id: str                # Short unique hex identifier (6 chars)
    name: str              # Human-readable skill name (e.g. "Rust", "Piano")
    target_seconds: int    # Total time budget in seconds
    created_at: str        # ISO 8601 timestamp of when the skill was created
    sessions: list[Session] = field(default_factory=list)  # List of completed sessions
    active_since: str | None = None  # ISO timestamp if timer is currently running, None otherwise


# --- JSON file I/O ---

def _load_raw() -> dict:
    """Read and parse the JSON data file. Returns empty structure if file missing or empty."""
    if not DATA_FILE.exists() or DATA_FILE.stat().st_size == 0:
        return {"skills": []}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_raw(data: dict) -> None:
    """Write the full data dictionary to the JSON file with pretty formatting."""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# --- Serialization helpers ---

def _skill_from_dict(d: dict) -> Skill:
    """Convert a raw dictionary (from JSON) into a Skill dataclass instance."""
    sessions = [Session(**s) for s in d.get("sessions", [])]
    return Skill(
        id=d["id"],
        name=d["name"],
        target_seconds=d["target_seconds"],
        created_at=d["created_at"],
        sessions=sessions,
        active_since=d.get("active_since"),
    )


def _skill_to_dict(skill: Skill) -> dict:
    """Convert a Skill dataclass instance into a plain dictionary for JSON serialization."""
    d = asdict(skill)
    return d


# --- Public CRUD operations ---

def load_skills() -> list[Skill]:
    """Load all skills from the data file and return as a list of Skill objects."""
    data = _load_raw()
    return [_skill_from_dict(s) for s in data["skills"]]


def save_skills(skills: list[Skill]) -> None:
    """Persist the full list of skills to the data file, overwriting previous contents."""
    _save_raw({"skills": [_skill_to_dict(s) for s in skills]})


def get_skill(skill_id: str) -> Skill | None:
    """Find and return a single skill by its ID, or None if not found."""
    for skill in load_skills():
        if skill.id == skill_id:
            return skill
    return None


def create_skill(name: str, target_seconds: int) -> Skill:
    """Create a new skill with the given name and time budget, save it, and return it."""
    skills = load_skills()
    # Generate a short random hex ID for the new skill
    skill = Skill(
        id=uuid.uuid4().hex[:6],
        name=name,
        target_seconds=target_seconds,
        created_at=datetime.now().isoformat(timespec="seconds"),
        sessions=[],
    )
    skills.append(skill)
    save_skills(skills)
    return skill


def delete_skill(skill_id: str) -> bool:
    """Delete a skill by ID. Returns True if found and deleted, False otherwise."""
    skills = load_skills()
    original_len = len(skills)
    # Filter out the skill to delete
    skills = [s for s in skills if s.id != skill_id]
    if len(skills) == original_len:
        return False  # Skill not found — nothing deleted
    save_skills(skills)
    return True


# --- Timer operations ---

def start_timer(skill_id: str) -> Skill | None:
    """Start the timer for a skill. Records the current time as active_since.
    Returns the skill if found (even if already running), or None if not found."""
    skills = load_skills()
    for skill in skills:
        if skill.id == skill_id:
            if skill.active_since is not None:
                return skill  # Timer already running — return without change
            # Record the current time as the timer start
            skill.active_since = datetime.now().isoformat(timespec="seconds")
            save_skills(skills)
            return skill
    return None  # Skill not found


def stop_timer(skill_id: str) -> Session | None:
    """Stop the timer for a skill, create a session from the elapsed time, and save it.
    Returns the new Session, or None if skill not found or timer wasn't running."""
    skills = load_skills()
    for skill in skills:
        if skill.id == skill_id:
            if skill.active_since is None:
                return None  # Timer not running — nothing to stop
            # Calculate elapsed time since timer was started
            start_dt = datetime.fromisoformat(skill.active_since)
            end_dt = datetime.now()
            duration = int((end_dt - start_dt).total_seconds())
            # Cap duration at remaining time so we don't exceed the target
            remaining = remaining_seconds(skill)
            if duration > remaining:
                duration = remaining
                end_dt = start_dt + timedelta(seconds=duration)
            # Create and record the session
            session = Session(
                start=skill.active_since,
                end=end_dt.isoformat(timespec="seconds"),
                duration_seconds=duration,
            )
            skill.sessions.append(session)
            skill.active_since = None  # Clear the running timer
            save_skills(skills)
            return session
    return None  # Skill not found


# --- Computed properties ---

def elapsed_seconds(skill: Skill) -> int:
    """Calculate total seconds spent across all sessions for a skill."""
    return sum(s.duration_seconds for s in skill.sessions)


def remaining_seconds(skill: Skill) -> int:
    """Calculate seconds remaining toward the skill's target. Never returns negative."""
    return max(0, skill.target_seconds - elapsed_seconds(skill))


# --- Formatting ---

def format_duration(total_seconds: int) -> str:
    """Format a duration in seconds as a human-readable string.
    Examples: 45 -> '45s', 90 -> '1m 30s', 3661 -> '1h 01m 01s'.
    Drops zero leading components (no '0h' prefix)."""
    h = total_seconds // 3600          # Extract hours
    m = (total_seconds % 3600) // 60   # Extract remaining minutes
    s = total_seconds % 60             # Extract remaining seconds
    parts = []
    if h:
        parts.append(f"{h}h")
    # Show minutes if there are any, or if hours exist (to avoid "1h 05s")
    if m or (h and not s):
        parts.append(f"{m:02d}m" if h else f"{m}m")
    parts.append(f"{s:02d}s")
    return " ".join(parts)

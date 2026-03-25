"""Data layer for LearnTracker — Skill/Session dataclasses and JSON persistence."""

import json
import os
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path

DATA_FILE = Path(__file__).parent / "data.json"


@dataclass
class Session:
    start: str
    end: str
    duration_seconds: int


@dataclass
class Skill:
    id: str
    name: str
    target_seconds: int
    created_at: str
    sessions: list[Session] = field(default_factory=list)
    active_since: str | None = None  # ISO timestamp if timer is currently running


def _load_raw() -> dict:
    if not DATA_FILE.exists() or DATA_FILE.stat().st_size == 0:
        return {"skills": []}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_raw(data: dict) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _skill_from_dict(d: dict) -> Skill:
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
    d = asdict(skill)
    return d


def load_skills() -> list[Skill]:
    data = _load_raw()
    return [_skill_from_dict(s) for s in data["skills"]]


def save_skills(skills: list[Skill]) -> None:
    _save_raw({"skills": [_skill_to_dict(s) for s in skills]})


def get_skill(skill_id: str) -> Skill | None:
    for skill in load_skills():
        if skill.id == skill_id:
            return skill
    return None


def create_skill(name: str, target_seconds: int) -> Skill:
    skills = load_skills()
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
    skills = load_skills()
    original_len = len(skills)
    skills = [s for s in skills if s.id != skill_id]
    if len(skills) == original_len:
        return False
    save_skills(skills)
    return True


def start_timer(skill_id: str) -> Skill | None:
    skills = load_skills()
    for skill in skills:
        if skill.id == skill_id:
            if skill.active_since is not None:
                return skill  # already running
            skill.active_since = datetime.now().isoformat(timespec="seconds")
            save_skills(skills)
            return skill
    return None


def stop_timer(skill_id: str) -> Session | None:
    skills = load_skills()
    for skill in skills:
        if skill.id == skill_id:
            if skill.active_since is None:
                return None  # not running
            start_dt = datetime.fromisoformat(skill.active_since)
            end_dt = datetime.now()
            duration = int((end_dt - start_dt).total_seconds())
            # Cap duration at remaining time
            remaining = remaining_seconds(skill)
            if duration > remaining:
                duration = remaining
                end_dt = start_dt + timedelta(seconds=duration)
            session = Session(
                start=skill.active_since,
                end=end_dt.isoformat(timespec="seconds"),
                duration_seconds=duration,
            )
            skill.sessions.append(session)
            skill.active_since = None
            save_skills(skills)
            return session
    return None


def elapsed_seconds(skill: Skill) -> int:
    return sum(s.duration_seconds for s in skill.sessions)


def remaining_seconds(skill: Skill) -> int:
    return max(0, skill.target_seconds - elapsed_seconds(skill))


def format_duration(total_seconds: int) -> str:
    h = total_seconds // 3600
    m = (total_seconds % 3600) // 60
    s = total_seconds % 60
    parts = []
    if h:
        parts.append(f"{h}h")
    if m or (h and not s):
        parts.append(f"{m:02d}m" if h else f"{m}m")
    parts.append(f"{s:02d}s")
    return " ".join(parts)

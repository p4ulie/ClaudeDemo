# LearnTracker — Proposal

## Overview

A web application for tracking time spent learning new skills. Users define timers with a target duration, start/stop them, and review session logs showing how time was spent.

## Core Concepts

- **Skill**: A learning topic (e.g. "Rust", "Piano") with a target time budget (e.g. 2 hours)
- **Timer**: A countdown timer attached to a skill. Counts down from the remaining budget when active.
- **Session**: A recorded period between activating and deactivating a timer. Stored with start time, end time, and duration.

## User Workflow

1. Create a skill with a name and target time (e.g. "Rust — 2h")
2. Click **Start** to begin the countdown timer
3. The timer counts down in real-time in the browser
4. Click **Stop** to end the session — the elapsed time is logged
5. View a log of all sessions per skill with human-readable timestamps and durations
6. See remaining time toward the goal at a glance

## Tech Stack

| Layer     | Choice                          |
|-----------|---------------------------------|
| Language  | Python 3.14                     |
| Backend   | Flask                           |
| Frontend  | Jinja2 templates + vanilla JS   |
| Storage   | JSON text file (`data.json`)    |
| Testing   | unittest (stdlib)               |

**Dependencies**: Flask only. No database, no ORM, no JS framework.

## Data Storage

A single `data.json` file in the project directory:

```json
{
  "skills": [
    {
      "id": "a1b2c3",
      "name": "Rust",
      "target_seconds": 7200,
      "created_at": "2026-03-25T10:00:00",
      "sessions": [
        {
          "start": "2026-03-25T10:05:00",
          "end": "2026-03-25T10:35:00",
          "duration_seconds": 1800
        }
      ]
    }
  ]
}
```

JSON chosen over CSV because sessions are nested under skills. The file is read on each request and written on each mutation — acceptable for single-user use.

## Architecture

```
LearnTracker/
├── app.py                  # Flask app factory, routes
├── models.py               # Skill, Session dataclasses; file read/write logic
├── static/
│   ├── style.css           # Minimal styling
│   └── timer.js            # Client-side countdown logic
├── templates/
│   ├── base.html           # Shared layout
│   ├── index.html          # Skill list with timers
│   └── log.html            # Session log per skill
├── tests/
│   ├── __init__.py
│   ├── test_models.py      # Data layer unit tests
│   └── test_routes.py      # Flask route integration tests
├── data.json               # Persisted skill/session data (git-ignored)
├── requirements.txt        # Flask
├── CLAUDE.md
├── PROPOSAL.md
└── README.md
```

### Module Responsibilities

- **models.py** — Pure data logic. Dataclasses for `Skill` and `Session`. Functions to load/save `data.json`, compute elapsed and remaining time. No Flask dependency — fully testable in isolation.
- **app.py** — Flask routes and template rendering. Thin layer that calls into `models.py`. Handles form submissions and JSON API endpoints for the timer.
- **timer.js** — Runs the countdown in the browser. On start, records a timestamp and ticks every second. On stop, posts elapsed time to the server. If the page is refreshed while a timer is running, the start timestamp is stored in `localStorage` so the countdown resumes correctly.

## Routes

| Method | Path                    | Description                        |
|--------|-------------------------|------------------------------------|
| GET    | `/`                     | List all skills with timer controls|
| POST   | `/skills`               | Create a new skill                 |
| POST   | `/skills/<id>/start`    | Start timer (record start time)    |
| POST   | `/skills/<id>/stop`     | Stop timer (save session)          |
| GET    | `/skills/<id>/log`      | View session log for a skill       |
| POST   | `/skills/<id>/delete`   | Delete a skill and its sessions    |

## Timer Behavior

- The countdown runs **client-side** in JavaScript for responsive UI
- Start/stop events are sent to the **server** to persist sessions
- The server is the source of truth for elapsed time — the JS timer is a visual aid
- If the browser is closed while a timer is running, the start time is saved server-side; on next visit, the timer resumes counting from that stored start time
- When remaining time reaches zero, the timer stops automatically and logs the session

## Session Log Format

The log page displays sessions in a human-readable table:

```
Rust — 1h 30m remaining of 2h 00m

Date                  Duration
2026-03-25 10:05      30m 00s
2026-03-25 14:20      15m 30s
                      --------
Total                 45m 30s
```

Durations formatted as `Xh Ym Zs`, dropping zero components (e.g. `30m 00s` not `0h 30m 00s`).

## Development Plan

### Phase 1 — Data layer
- `models.py` with Skill/Session dataclasses and JSON file read/write
- Unit tests for model operations (create, start, stop, compute remaining)

### Phase 2 — Flask routes
- `app.py` with all routes
- Jinja2 templates for skill list and session log
- Integration tests with Flask test client

### Phase 3 — Client-side timer
- `timer.js` with countdown display, localStorage persistence
- `style.css` with clean minimal layout

### Phase 4 — Polish
- Input validation (duplicate names, negative times)
- Edge cases (timer already running, target reached)
- README with setup instructions

# LearnTracker

A web app for tracking time spent learning new skills. Define skills with target durations, run countdown timers, and review session logs.

## Setup

```bash
pip install -r requirements.txt
python app.py
```

Open http://localhost:5000 in your browser.

## Usage

1. Add a skill with a name and target time (e.g. "Rust — 2h")
2. Click **Start** to begin the countdown timer
3. Click **Stop** to end the session — elapsed time is logged
4. Click **Log** to view all sessions for a skill
5. Remaining time updates automatically

## Running Tests

```bash
python -m unittest discover tests -v
```

## Tech Stack

- Python 3.14 + Flask
- Jinja2 templates + vanilla JavaScript
- JSON file storage (`data.json`, git-ignored)

## License

GPL-3.0

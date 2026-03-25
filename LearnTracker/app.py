"""Flask application for LearnTracker — routes, templates, and JSON API."""

from flask import Flask, render_template, request, redirect, url_for, jsonify, send_from_directory

import models


def create_app() -> Flask:
    """Application factory — creates and configures the Flask app with all routes."""
    app = Flask(__name__)

    # --- Service worker route (must be served from root for full scope) ---

    @app.route("/sw.js")
    def service_worker():
        """Serve the service worker from the root URL for proper PWA scope."""
        return send_from_directory(app.static_folder, "sw.js",
                                   mimetype="application/javascript")

    # --- HTML routes (server-rendered pages) ---

    @app.route("/")
    def index():
        """Home page — display all skills with timer controls and progress."""
        skills = models.load_skills()
        # Attach computed display values to each skill for use in the template
        for skill in skills:
            skill._elapsed = models.elapsed_seconds(skill)
            skill._remaining = models.remaining_seconds(skill)
            skill._elapsed_fmt = models.format_duration(skill._elapsed)
            skill._remaining_fmt = models.format_duration(skill._remaining)
            skill._target_fmt = models.format_duration(skill.target_seconds)
        return render_template("index.html", skills=skills)

    @app.route("/skills", methods=["POST"])
    def create_skill():
        """Handle form submission to create a new skill."""
        # Extract and validate form inputs
        name = request.form.get("name", "").strip()
        hours = request.form.get("hours", "0")
        minutes = request.form.get("minutes", "0")
        try:
            h = int(hours)
            m = int(minutes)
        except ValueError:
            # Invalid numeric input — redirect back without creating
            return redirect(url_for("index"))
        # Convert hours + minutes to total seconds
        total = h * 3600 + m * 60
        # Reject empty names or zero/negative durations
        if not name or total <= 0:
            return redirect(url_for("index"))
        models.create_skill(name, total)
        return redirect(url_for("index"))

    @app.route("/skills/<skill_id>/start", methods=["POST"])
    def start_timer(skill_id):
        """Start the timer for a skill (HTML form fallback)."""
        models.start_timer(skill_id)
        return redirect(url_for("index"))

    @app.route("/skills/<skill_id>/stop", methods=["POST"])
    def stop_timer(skill_id):
        """Stop the timer for a skill (HTML form fallback)."""
        models.stop_timer(skill_id)
        return redirect(url_for("index"))

    @app.route("/skills/<skill_id>/log")
    def skill_log(skill_id):
        """Session log page — shows all recorded sessions for a single skill."""
        skill = models.get_skill(skill_id)
        if skill is None:
            # Skill not found — redirect to home
            return redirect(url_for("index"))
        # Attach computed display values for the template
        skill._elapsed = models.elapsed_seconds(skill)
        skill._remaining = models.remaining_seconds(skill)
        skill._remaining_fmt = models.format_duration(skill._remaining)
        skill._target_fmt = models.format_duration(skill.target_seconds)
        # Format each session's duration for display
        for session in skill.sessions:
            session._duration_fmt = models.format_duration(session.duration_seconds)
        # Calculate total logged time across all sessions
        total_logged = sum(s.duration_seconds for s in skill.sessions)
        return render_template(
            "log.html",
            skill=skill,
            total_fmt=models.format_duration(total_logged),
        )

    @app.route("/skills/<skill_id>/delete", methods=["POST"])
    def delete_skill(skill_id):
        """Delete a skill and all its sessions."""
        models.delete_skill(skill_id)
        return redirect(url_for("index"))

    # --- JSON API endpoints (used by timer.js for async timer control) ---

    @app.route("/api/skills/<skill_id>/start", methods=["POST"])
    def api_start(skill_id):
        """API: Start a skill's timer. Returns the active_since timestamp."""
        skill = models.start_timer(skill_id)
        if skill is None:
            return jsonify({"error": "not found"}), 404
        return jsonify({"active_since": skill.active_since})

    @app.route("/api/skills/<skill_id>/stop", methods=["POST"])
    def api_stop(skill_id):
        """API: Stop a skill's timer. Returns the recorded session details."""
        session = models.stop_timer(skill_id)
        if session is None:
            return jsonify({"error": "not running"}), 400
        return jsonify({
            "duration_seconds": session.duration_seconds,
            "start": session.start,
            "end": session.end,
        })

    @app.route("/api/skills/<skill_id>")
    def api_skill(skill_id):
        """API: Get current state of a skill (remaining time, active timer, etc.)."""
        skill = models.get_skill(skill_id)
        if skill is None:
            return jsonify({"error": "not found"}), 404
        return jsonify({
            "id": skill.id,
            "name": skill.name,
            "target_seconds": skill.target_seconds,
            "remaining_seconds": models.remaining_seconds(skill),
            "active_since": skill.active_since,
        })

    return app


# Run the development server when executed directly
if __name__ == "__main__":
    create_app().run(debug=True)

"""Flask application for LearnTracker."""

from flask import Flask, render_template, request, redirect, url_for, jsonify

import models


def create_app() -> Flask:
    app = Flask(__name__)

    @app.route("/")
    def index():
        skills = models.load_skills()
        for skill in skills:
            skill._elapsed = models.elapsed_seconds(skill)
            skill._remaining = models.remaining_seconds(skill)
            skill._elapsed_fmt = models.format_duration(skill._elapsed)
            skill._remaining_fmt = models.format_duration(skill._remaining)
            skill._target_fmt = models.format_duration(skill.target_seconds)
        return render_template("index.html", skills=skills)

    @app.route("/skills", methods=["POST"])
    def create_skill():
        name = request.form.get("name", "").strip()
        hours = request.form.get("hours", "0")
        minutes = request.form.get("minutes", "0")
        try:
            h = int(hours)
            m = int(minutes)
        except ValueError:
            return redirect(url_for("index"))
        total = h * 3600 + m * 60
        if not name or total <= 0:
            return redirect(url_for("index"))
        models.create_skill(name, total)
        return redirect(url_for("index"))

    @app.route("/skills/<skill_id>/start", methods=["POST"])
    def start_timer(skill_id):
        models.start_timer(skill_id)
        return redirect(url_for("index"))

    @app.route("/skills/<skill_id>/stop", methods=["POST"])
    def stop_timer(skill_id):
        models.stop_timer(skill_id)
        return redirect(url_for("index"))

    @app.route("/skills/<skill_id>/log")
    def skill_log(skill_id):
        skill = models.get_skill(skill_id)
        if skill is None:
            return redirect(url_for("index"))
        skill._elapsed = models.elapsed_seconds(skill)
        skill._remaining = models.remaining_seconds(skill)
        skill._remaining_fmt = models.format_duration(skill._remaining)
        skill._target_fmt = models.format_duration(skill.target_seconds)
        for session in skill.sessions:
            session._duration_fmt = models.format_duration(session.duration_seconds)
        total_logged = sum(s.duration_seconds for s in skill.sessions)
        return render_template(
            "log.html",
            skill=skill,
            total_fmt=models.format_duration(total_logged),
        )

    @app.route("/skills/<skill_id>/delete", methods=["POST"])
    def delete_skill(skill_id):
        models.delete_skill(skill_id)
        return redirect(url_for("index"))

    # JSON API for timer.js
    @app.route("/api/skills/<skill_id>/start", methods=["POST"])
    def api_start(skill_id):
        skill = models.start_timer(skill_id)
        if skill is None:
            return jsonify({"error": "not found"}), 404
        return jsonify({"active_since": skill.active_since})

    @app.route("/api/skills/<skill_id>/stop", methods=["POST"])
    def api_stop(skill_id):
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


if __name__ == "__main__":
    create_app().run(debug=True)

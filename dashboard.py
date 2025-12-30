"""Flask dashboard for scale measurements."""

from flask import Flask, jsonify, render_template, request

import db
from config import BASE_DIR, DASHBOARD_HOST, DASHBOARD_PORT
from etl import run_etl

app = Flask(__name__, template_folder=BASE_DIR / "templates")


@app.route("/")
def index():
    """Render the dashboard."""
    run_etl()  # Process any new packets

    # Get profile filter from query param
    profile_param = request.args.get("profile")
    profile_id = int(profile_param) if profile_param and profile_param.isdigit() else None

    latest = db.get_latest_measurement(profile_id=profile_id)
    recent = db.get_measurements(limit=10, profile_id=profile_id)
    profiles = db.get_profiles()

    return render_template(
        "index.html",
        latest=latest,
        recent=recent,
        profiles=profiles,
        selected_profile=profile_id,
    )


@app.route("/api/chart-data")
def chart_data():
    """Return chart data as JSON."""
    profile_param = request.args.get("profile")
    profile_id = int(profile_param) if profile_param and profile_param.isdigit() else None

    measurements = db.get_measurements_since(days=30, profile_id=profile_id)
    return jsonify(
        {
            "labels": [m["timestamp"][:10] for m in measurements],
            "weights": [m["weight_kg"] for m in measurements],
            "body_fat": [m["body_fat_pct"] for m in measurements],
        }
    )


# Profile API routes
@app.route("/api/profiles", methods=["GET"])
def list_profiles():
    """Return list of profiles."""
    profiles = db.get_profiles()
    return jsonify(profiles)


@app.route("/api/profiles", methods=["POST"])
def create_profile():
    """Create a new profile."""
    data = request.get_json()
    if not data or not data.get("name"):
        return jsonify({"error": "Name is required"}), 400

    profile_id = db.save_profile(
        name=data["name"],
        scale_user_id=data.get("scale_user_id"),
        height_cm=data.get("height_cm"),
        age=data.get("age"),
        gender=data.get("gender"),
    )
    return jsonify({"id": profile_id}), 201


@app.route("/api/profiles/<int:profile_id>", methods=["GET"])
def get_profile(profile_id: int):
    """Get a single profile."""
    profile = db.get_profile(profile_id)
    if not profile:
        return jsonify({"error": "Profile not found"}), 404
    return jsonify(profile)


@app.route("/api/profiles/<int:profile_id>", methods=["PUT"])
def update_profile(profile_id: int):
    """Update an existing profile."""
    data = request.get_json()
    if not data or not data.get("name"):
        return jsonify({"error": "Name is required"}), 400

    existing = db.get_profile(profile_id)
    if not existing:
        return jsonify({"error": "Profile not found"}), 404

    db.save_profile(
        name=data["name"],
        scale_user_id=data.get("scale_user_id"),
        height_cm=data.get("height_cm"),
        age=data.get("age"),
        gender=data.get("gender"),
        profile_id=profile_id,
    )
    return jsonify({"id": profile_id})


@app.route("/api/profiles/<int:profile_id>", methods=["DELETE"])
def delete_profile_route(profile_id: int):
    """Delete a profile."""
    existing = db.get_profile(profile_id)
    if not existing:
        return jsonify({"error": "Profile not found"}), 404

    db.delete_profile(profile_id)
    return jsonify({"deleted": True})


# HTMX partial routes
@app.route("/partials/profiles")
def partials_profiles():
    """Render profiles list partial."""
    profiles = db.get_profiles()
    return render_template("partials/profiles.html", profiles=profiles)


@app.route("/partials/profile-form")
@app.route("/partials/profile-form/<int:profile_id>")
def partials_profile_form(profile_id: int | None = None):
    """Render profile form partial."""
    profile = db.get_profile(profile_id) if profile_id else None
    return render_template("partials/profile_form.html", profile=profile)


@app.route("/partials/profiles", methods=["POST"])
def partials_create_profile():
    """Create profile and return updated list."""
    db.save_profile(
        name=request.form["name"],
        scale_user_id=int(request.form["scale_user_id"]) if request.form.get("scale_user_id") else None,
        height_cm=int(request.form["height_cm"]) if request.form.get("height_cm") else None,
        age=int(request.form["age"]) if request.form.get("age") else None,
        gender=request.form.get("gender") or None,
    )
    profiles = db.get_profiles()
    return render_template("partials/profiles.html", profiles=profiles)


@app.route("/partials/profiles/<int:profile_id>", methods=["PUT"])
def partials_update_profile(profile_id: int):
    """Update profile and return updated list."""
    db.save_profile(
        name=request.form["name"],
        scale_user_id=int(request.form["scale_user_id"]) if request.form.get("scale_user_id") else None,
        height_cm=int(request.form["height_cm"]) if request.form.get("height_cm") else None,
        age=int(request.form["age"]) if request.form.get("age") else None,
        gender=request.form.get("gender") or None,
        profile_id=profile_id,
    )
    profiles = db.get_profiles()
    return render_template("partials/profiles.html", profiles=profiles)


@app.route("/partials/profiles/<int:profile_id>", methods=["DELETE"])
def partials_delete_profile(profile_id: int):
    """Delete profile and return updated list."""
    db.delete_profile(profile_id)
    profiles = db.get_profiles()
    return render_template("partials/profiles.html", profiles=profiles)


if __name__ == "__main__":
    db.migrate_db()  # Run migrations first for existing databases
    db.init_db()
    app.run(host=DASHBOARD_HOST, port=DASHBOARD_PORT, debug=False)

"""Flask dashboard for scale measurements."""

from flask import Flask, jsonify, render_template

import db
from config import BASE_DIR, DASHBOARD_HOST, DASHBOARD_PORT

app = Flask(__name__, template_folder=BASE_DIR / "templates")


@app.route("/")
def index():
    """Render the dashboard."""
    latest = db.get_latest_measurement()
    recent = db.get_measurements(limit=10)
    return render_template("index.html", latest=latest, recent=recent)


@app.route("/api/chart-data")
def chart_data():
    """Return chart data as JSON."""
    measurements = db.get_measurements_since(days=30)
    return jsonify(
        {
            "labels": [m["timestamp"][:10] for m in measurements],
            "weights": [m["weight_kg"] for m in measurements],
            "body_fat": [m["body_fat_pct"] for m in measurements],
        }
    )


if __name__ == "__main__":
    db.init_db()
    app.run(host=DASHBOARD_HOST, port=DASHBOARD_PORT, debug=False)

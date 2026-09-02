from flask import Flask, jsonify, render_template, request, session
from dotenv import load_dotenv
import os
import secrets

from routes.auth import auth_bp
from routes.dashboard import dashboard_bp
from routes.notifications import notification_bp
from routes.reports import reports_bp
from routes.kra_kpi_routes import kra_kpi_bp


load_dotenv()


app = Flask(__name__)

secret_key = os.getenv("SECRET_KEY")

if not secret_key:
    raise RuntimeError("SECRET_KEY must be set in the environment.")

app_environment = os.getenv("APP_ENV", "production").lower()

app.config.update(
    SECRET_KEY=secret_key,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=app_environment == "production"
)


def get_csrf_token():
    """Return the session-bound token used to protect unsafe requests."""
    token = session.get("_csrf_token")

    if token is None:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token

    return token


@app.context_processor
def inject_csrf_token():
    return {"csrf_token": get_csrf_token}


@app.before_request
def validate_csrf_token():
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return None

    submitted_token = (
        request.headers.get("X-CSRF-Token")
        or request.form.get("csrf_token")
    )
    expected_token = session.get("_csrf_token")

    if (
        not submitted_token
        or not expected_token
        or not secrets.compare_digest(submitted_token, expected_token)
    ):
        if request.path.startswith("/api/"):
            return jsonify({
                "success": False,
                "message": "Invalid or missing CSRF token."
            }), 400

        return "Invalid or missing CSRF token.", 400

    return None


# ==============================
# REGISTER BLUEPRINTS
# ==============================

app.register_blueprint(
    auth_bp,
    url_prefix="/api/auth"
)

app.register_blueprint(
    dashboard_bp
)

app.register_blueprint(
    notification_bp,
    url_prefix="/api/notifications"
)

app.register_blueprint(
    reports_bp,
    url_prefix="/api/reports"
)
app.register_blueprint(kra_kpi_bp)


# ==============================
# LANDING PAGE
# ==============================

@app.route("/")
def landing_page():

    return render_template(
        "login.html"
    )


# ==============================
# LOGIN PAGE
# ==============================

@app.route("/login")
def login_page():

    return render_template(
        "login.html"
    )


# ==============================
# HEALTH CHECK
# ==============================

@app.route("/api/health")
def health():

    return jsonify({
        "status": "ok"
    })


@app.route("/api/csrf-token")
def csrf_token():
    return jsonify({
        "csrf_token": get_csrf_token()
    })


# ==============================
# RUN APPLICATION
# ==============================
if __name__ == "__main__":

    app.run(
        debug=app_environment == "development",
        host="127.0.0.1",
        port=5000
    )

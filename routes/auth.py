from flask import Blueprint, request, jsonify, session
from werkzeug.security import check_password_hash

from config import get_db_connection


auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["POST"])
def login():

    data = request.get_json()

    if not data:
        return jsonify({
            "success": False,
            "message": "Invalid request."
        }), 400

    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        return jsonify({
            "success": False,
            "message": "Username and password are required."
        }), 400

    connection = None

    try:

        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT
                u.user_id,
                u.username,
                u.password,
                u.role_id,
                r.role_name
            FROM users u
            INNER JOIN roles r
                ON u.role_id = r.role_id
            WHERE LOWER(u.username) = LOWER(%s)
        """, (username,))

        user = cursor.fetchone()

        cursor.close()

        if user is None:

            return jsonify({
                "success": False,
                "message": "Invalid username or password."
            }), 401

        (
            user_id,
            username,
            password_hash,
            role_id,
            role_name
        ) = user

        # Verify hashed password
        if not check_password_hash(
            password_hash,
            password
        ):

            return jsonify({
                "success": False,
                "message": "Invalid username or password."
            }), 401

        # Create session
        session.clear()

        session["user_id"] = user_id
        session["username"] = username
        session["role_id"] = role_id
        session["role_name"] = role_name

        return jsonify({

            "success": True,

            "message": "Login successful.",

            "user": {
                "user_id": user_id,
                "username": username,
                "role_id": role_id,
                "role": role_name
            }

        }), 200

    except Exception as e:

        print("LOGIN ERROR:", e)

        return jsonify({
            "success": False,
            "message": "Server/database error."
        }), 500

    finally:

        if connection:
            connection.close()


@auth_bp.route("/logout", methods=["POST"])
def logout():

    session.clear()

    return jsonify({
        "success": True,
        "message": "Logged out successfully."
    })


@auth_bp.route("/me", methods=["GET"])
def current_user():

    if "user_id" not in session:

        return jsonify({
            "authenticated": False
        }), 401

    return jsonify({

        "authenticated": True,

        "user": {
            "user_id": session["user_id"],
            "username": session["username"],
            "role_id": session["role_id"],
            "role": session["role_name"]
        }

    })
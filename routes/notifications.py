from flask import Blueprint, jsonify, session
from config import get_db_connection


notification_bp = Blueprint(
    "notifications",
    __name__
)
# ============================================================
# CREATE NOTIFICATION
# ============================================================

def create_notification(
    user_id,
    title,
    message,
    notification_type="system"
):

    conn = None
    cursor = None

    try:
        conn = get_db_connection()

        if conn is None:
            print("Notification creation failed: database connection failed.")
            return False

        cursor = conn.cursor()

        # Prevent duplicate identical unread notifications
        cursor.execute("""
            SELECT notification_id FROM notifications
            WHERE user_id = %s AND title = %s AND message = %s AND is_read = FALSE
        """, (user_id, title, message))
        if cursor.fetchone():
            return True

        cursor.execute("""
            INSERT INTO notifications (
                user_id,
                title,
                message,
                notification_type,
                is_read,
                created_at
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                FALSE,
                CURRENT_TIMESTAMP
            )
        """, (
            user_id,
            title,
            message,
            notification_type
        ))

        conn.commit()

        return True

    except Exception as e:

        if conn:
            conn.rollback()

        print(
            "Notification creation error:",
            e
        )

        return False

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()

# ============================================================
# TEST
# ============================================================

@notification_bp.route("/test", methods=["GET"])
def notification_test():

    return jsonify({
        "success": True,
        "message": "Notification API is working."
    })


# ============================================================
# GET NOTIFICATIONS
# ============================================================

@notification_bp.route("/", methods=["GET"])
def get_notifications():

    if "user_id" not in session:
        return jsonify({
            "success": False,
            "message": "User not logged in."
        }), 401

    user_id = session["user_id"]

    conn = None
    cursor = None

    try:

        conn = get_db_connection()

        if conn is None:
            return jsonify({
                "success": False,
                "message": "Database connection failed."
            }), 500

        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                notification_id,
                title,
                message,
                notification_type,
                is_read,
                created_at
            FROM notifications
            WHERE user_id = %s
            ORDER BY created_at DESC
        """, (user_id,))

        rows = cursor.fetchall()

        seen_keys = set()
        notifications = []

        for row in rows:
            clean_title = (row[1] or "").strip()
            clean_msg = (row[2] or "").strip()
            key = (clean_title, clean_msg)
            if key in seen_keys:
                continue
            seen_keys.add(key)

            notifications.append({
                "id": row[0],
                "title": row[1],
                "message": row[2],
                "type": row[3],
                "is_read": row[4],
                "created_at":
                    row[5].isoformat()
                    if row[5] else None
            })

        return jsonify({
            "success": True,
            "notifications": notifications
        })

    except Exception as e:

        print("Notification error:", e)

        return jsonify({
            "success": False,
            "message": "Failed to load notifications."
        }), 500

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()


# ============================================================
# MARK ONE NOTIFICATION AS READ
# ============================================================

@notification_bp.route(
    "/<int:notification_id>/read",
    methods=["POST"]
)
def mark_notification_read(notification_id):

    if "user_id" not in session:
        return jsonify({
            "success": False,
            "message": "User not logged in."
        }), 401

    user_id = session["user_id"]

    conn = None
    cursor = None

    try:

        conn = get_db_connection()

        if conn is None:
            return jsonify({
                "success": False,
                "message": "Database connection failed."
            }), 500

        cursor = conn.cursor()

        cursor.execute("""
            UPDATE notifications
            SET is_read = TRUE
            WHERE notification_id = %s
              AND user_id = %s
        """, (
            notification_id,
            user_id
        ))

        if cursor.rowcount == 0:

            conn.rollback()

            return jsonify({
                "success": False,
                "message": "Notification not found."
            }), 404

        conn.commit()

        return jsonify({
            "success": True,
            "message": "Notification marked as read."
        })

    except Exception as e:

        if conn:
            conn.rollback()

        print(
            "Mark notification read error:",
            e
        )

        return jsonify({
            "success": False,
            "message": "Failed to update notification."
        }), 500

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()


# ============================================================
# MARK ALL NOTIFICATIONS AS READ
# ============================================================

@notification_bp.route(
    "/read-all",
    methods=["POST"]
)
def mark_all_notifications_read():

    if "user_id" not in session:
        return jsonify({
            "success": False,
            "message": "User not logged in."
        }), 401

    user_id = session["user_id"]

    conn = None
    cursor = None

    try:

        conn = get_db_connection()

        if conn is None:
            return jsonify({
                "success": False,
                "message": "Database connection failed."
            }), 500

        cursor = conn.cursor()

        cursor.execute("""
            UPDATE notifications
            SET is_read = TRUE
            WHERE user_id = %s
              AND is_read = FALSE
        """, (user_id,))

        updated_count = cursor.rowcount

        conn.commit()

        return jsonify({
            "success": True,
            "message": "All notifications marked as read.",
            "updated_count": updated_count
        })

    except Exception as e:

        if conn:
            conn.rollback()

        print(
            "Mark all notifications read error:",
            e
        )

        return jsonify({
            "success": False,
            "message": "Failed to update notifications."
        }), 500

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()
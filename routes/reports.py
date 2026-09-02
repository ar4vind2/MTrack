from flask import Blueprint, jsonify

reports_bp = Blueprint(
    "reports",
    __name__
)


@reports_bp.route("/test")
def reports_test():

    return jsonify({
        "success": True,
        "message": "Reports API is working."
    })
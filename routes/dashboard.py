from flask import (
    Blueprint,
    jsonify,
    session,
    render_template,
    redirect,
    url_for,
    request
)

from config import get_db_connection


dashboard_bp = Blueprint(
    "dashboard",
    __name__
)


# Page-to-role mapping for the screens that are currently presentation-led.
# Keeping the mapping explicit prevents arbitrary templates being rendered from
# a URL while allowing the existing .html navigation links to keep working.
ADDITIONAL_PAGES = {
    "appraisal-form": ("appraisal_form.html", {"employee"}),
    "appraisal_form.html": ("appraisal_form.html", {"employee"}),
    "employee-attendance": ("employee_attendance.html", {"employee"}),
    "employee_attendance.html": ("employee_attendance.html", {"employee"}),
    "employee-goals": ("employee_goals.html", {"employee"}),
    "employee_goals.html": ("employee_goals.html", {"employee"}),
    "employee-training": ("employee_training.html", {"employee"}),
    "employee_training.html": ("employee_training.html", {"employee"}),
    "leave-request": ("leave_request.html", {"employee"}),
    "leave_request.html": ("leave_request.html", {"employee"}),
    "my-appraisals": ("my_appraisals.html", {"employee"}),
    "my_appraisals.html": ("my_appraisals.html", {"employee"}),
    "self-appraisal": ("self_appraisal.html", {"employee"}),
    "self_appraisal.html": ("self_appraisal.html", {"employee"}),
    "behaviour-rating": ("behaviour_rating.html", {"manager"}),
    "behaviour_rating.html": ("behaviour_rating.html", {"manager"}),
    "feedback-360": ("feedback_360.html", {"manager"}),
    "feedback_360.html": ("feedback_360.html", {"manager"}),
    "review-attendance": ("review_attendance.html", {"manager"}),
    "review_attendance.html": ("review_attendance.html", {"manager"}),
    "hr-dashboard": ("hr_dashboard.html", {"hr", "admin"}),
    "hr_dashboard.html": ("hr_dashboard.html", {"hr", "admin"}),
    "manage-training": ("manage_training.html", {"hr", "admin"}),
    "manage_training.html": ("manage_training.html", {"hr", "admin"}),
    "performance-results": ("performance_results.html", {"hr", "admin"}),
    "performance_results.html": ("performance_results.html", {"hr", "admin"}),
    "employee-performance-details": (
        "employee_performance_details.html",
        {"hr", "admin"}
    ),
    "employee_performance_details.html": (
        "employee_performance_details.html",
        {"hr", "admin"}
    ),
    "training-details": ("training_details.html", {"hr", "admin"}),
    "training_details.html": ("training_details.html", {"hr", "admin"}),
    "kra-kpi-report": ("kra_kpi_report.html", {"hr", "admin"}),
    "kra_kpi_report.html": ("kra_kpi_report.html", {"hr", "admin"}),
    "profile": ("profile.html", {"employee", "manager", "hr", "admin"}),
    "profile.html": ("profile.html", {"employee", "manager", "hr", "admin"}),
    "employee_dashboard.html": ("employee_dashboard.html", {"employee"}),
    "manager_dashboard.html": ("manager_dashboard.html", {"manager"}),
    "team_evaluation.html": ("team_evaluation.html", {"manager"}),
    "review_appraisal.html": ("review_appraisal.html", {"manager"}),
    "admin-dashboard": ("hr_dashboard.html", {"admin"}),
    "admin_dashboard.html": ("hr_dashboard.html", {"admin"}),
    "login.html": ("login.html", None),
}


def _render_additional_page(template_name, allowed_roles):
    if allowed_roles is None:
        return render_template(template_name)

    if "user_id" not in session:
        return redirect(url_for("login_page"))

    if session.get("role_name", "").lower() not in allowed_roles:
        return "Access Denied", 403

    return render_template(template_name)


@dashboard_bp.route("/<page_name>")
def additional_page(page_name):
    """Serve only the explicitly registered, role-protected UI screens."""
    if page_name == "index.html":
        return redirect(url_for("login_page"))

    page = ADDITIONAL_PAGES.get(page_name)

    if page is None:
        return "Not Found", 404

    return _render_additional_page(*page)


# ============================================================
# EMPLOYEE DASHBOARD PAGE
# ============================================================

@dashboard_bp.route("/employee-dashboard")
def employee_dashboard():

    if "user_id" not in session:
        return redirect(url_for("login_page"))

    role = session.get("role_name", "").lower()

    if role != "employee":
        return "Access Denied", 403

    return render_template("employee_dashboard.html")
# ============================================================
# MANAGER DASHBOARD PAGE
# ============================================================

@dashboard_bp.route("/manager-dashboard")
def manager_dashboard_page():

    if "user_id" not in session:
        return redirect(url_for("login_page"))

    role = session.get("role_name", "").lower()

    if role != "manager":
        return "Access Denied", 403

    return render_template("manager_dashboard.html")
# ============================================================
# MANAGER TEAM EVALUATION PAGE
# ============================================================

@dashboard_bp.route("/team-evaluation")
def team_evaluation_page():

    if "user_id" not in session:
        return redirect(url_for("login_page"))

    role = session.get("role_name", "").lower()

    if role != "manager":
        return "Access Denied", 403

    return render_template("team_evaluation.html")


# ============================================================
# MANAGER REVIEW APPRAISAL PAGE
# ============================================================

@dashboard_bp.route("/review-appraisal")
def review_appraisal_page():

    if "user_id" not in session:
        return redirect(url_for("login_page"))

    role = session.get("role_name", "").lower()

    if role != "manager":
        return "Access Denied", 403

    return render_template("review_appraisal.html")
# ============================================================
# EMPLOYEE DASHBOARD DATA
# ============================================================

@dashboard_bp.route("/employee", methods=["GET"])
def employee_dashboard_data():

    if "user_id" not in session:
        return jsonify({
            "success": False,
            "message": "Login required."
        }), 401

    # --------------------------------------------------------
    # Find employee record using logged-in user's user_id
    # --------------------------------------------------------

    user_id = session["user_id"]

    connection = None

    try:

        connection = get_db_connection()

        cursor = connection.cursor()

        # ----------------------------------------------------
        # Employee information
        # ----------------------------------------------------

        cursor.execute("""
            SELECT
                e.employee_id,
                e.employee_code,
                e.first_name,
                e.last_name,
                e.email,
                e.department_id,
                e.designation_id
            FROM employees e
            WHERE e.user_id = %s
        """, (user_id,))

        employee = cursor.fetchone()

        if employee is None:

            return jsonify({
                "success": False,
                "message": "Employee record not found."
            }), 404

        (
            employee_id,
            employee_code,
            first_name,
            last_name,
            email,
            department_id,
            designation_id
        ) = employee

        # ----------------------------------------------------
        # Department
        # ----------------------------------------------------

        cursor.execute("""
            SELECT department_name
            FROM departments
            WHERE department_id = %s
        """, (department_id,))

        department_result = cursor.fetchone()

        department = (
            department_result[0]
            if department_result
            else "Not Assigned"
        )

        # ----------------------------------------------------
        # Designation
        # ----------------------------------------------------

        cursor.execute("""
            SELECT designation_name
            FROM designations
            WHERE designation_id = %s
        """, (designation_id,))

        designation_result = cursor.fetchone()

        designation = (
            designation_result[0]
            if designation_result
            else "Not Assigned"
        )

        # ----------------------------------------------------
        # Latest performance result
        # ----------------------------------------------------

        cursor.execute("""
            SELECT
                appraisal_year,
                kpi_score,
                attendance_score,
                manager_score,
                behaviour_score,
                self_appraisal_score,
                training_score,
                final_score,
                rating,
                recommendation
            FROM performance_result
            WHERE employee_id = %s
            ORDER BY appraisal_year DESC, created_at DESC
            LIMIT 1
        """, (employee_id,))

        performance = cursor.fetchone()

        if performance:

            (
                appraisal_year,
                kpi_score,
                attendance_score,
                manager_score,
                behaviour_score,
                self_appraisal_score,
                training_score,
                final_score,
                rating,
                recommendation
            ) = performance

        else:

            appraisal_year = None
            kpi_score = 0
            attendance_score = 0
            manager_score = 0
            behaviour_score = 0
            self_appraisal_score = 0
            training_score = 0
            final_score = 0
            rating = "Not Available"
            recommendation = "Not Available"

        # ----------------------------------------------------
        # Performance trend
        # ----------------------------------------------------

        cursor.execute("""
            SELECT
                appraisal_year,
                final_score
            FROM performance_result
            WHERE employee_id = %s
            ORDER BY appraisal_year ASC
        """, (employee_id,))

        trend_rows = cursor.fetchall()

        performance_trend = []

        for row in trend_rows:

            performance_trend.append({
                "year": row[0],
                "score": float(row[1] or 0)
            })

        # ----------------------------------------------------
        # Attendance
        # ----------------------------------------------------

        cursor.execute("""
            SELECT
                COUNT(*) FILTER (
                    WHERE LOWER(status) = 'present'
                ),
                COUNT(*) FILTER (
                    WHERE LOWER(status) = 'absent'
                ),
                COUNT(*) FILTER (
                    WHERE LOWER(status) = 'leave'
                ),
                COUNT(*)
            FROM attendance
            WHERE employee_id = %s
        """, (employee_id,))

        attendance_result = cursor.fetchone()

        present = attendance_result[0] or 0
        absent = attendance_result[1] or 0
        leave = attendance_result[2] or 0
        total_days = attendance_result[3] or 0

        if total_days > 0:

            attendance_percentage = (
                present / total_days
            ) * 100

        else:

            attendance_percentage = 0

        # ----------------------------------------------------
        # KRA summary
        # ----------------------------------------------------

        cursor.execute("""
            SELECT
                COUNT(*),
                COUNT(*) FILTER (
                    WHERE LOWER(status) = 'completed'
                ),
                COUNT(*) FILTER (
                    WHERE LOWER(status) = 'pending'
                )
            FROM employee_kra
            WHERE employee_id = %s
        """, (employee_id,))

        kra_result = cursor.fetchone()

        total_kra = kra_result[0] or 0
        completed_kra = kra_result[1] or 0
        pending_kra = kra_result[2] or 0

        if total_kra > 0:

            kra_completion = (
                completed_kra / total_kra
            ) * 100

        else:

            kra_completion = 0

        # ----------------------------------------------------
        # Training summary
        # ----------------------------------------------------

        cursor.execute("""
            SELECT
                COUNT(*),
                COUNT(*) FILTER (
                    WHERE LOWER(status) = 'completed'
                )
            FROM training_records
            WHERE employee_id = %s
        """, (employee_id,))

        training_result = cursor.fetchone()

        total_training = training_result[0] or 0
        completed_training = training_result[1] or 0

        # ----------------------------------------------------
        # Notifications
        # ----------------------------------------------------

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
            LIMIT 5
        """, (user_id,))

        notification_rows = cursor.fetchall()

        notifications = []

        for row in notification_rows:

            notifications.append({
                "id": row[0],
                "title": row[1],
                "message": row[2],
                "type": row[3],
                "is_read": row[4],
                "created_at": row[5].isoformat()
            })

        cursor.close()

        # ====================================================
        # RESPONSE
        # ====================================================

        return jsonify({

            "success": True,

            "employee": {
                "id": employee_id,
                "employee_code": employee_code,
                "name": f"{first_name} {last_name}",
                "email": email,
                "department": department,
                "designation": designation
            },

            "performance": {

                "year": appraisal_year,

                "kpi_score": float(kpi_score or 0),

                "attendance_score":
                    float(attendance_score or 0),

                "manager_score":
                    float(manager_score or 0),

                "behaviour_score":
                    float(behaviour_score or 0),

                "self_appraisal_score":
                    float(self_appraisal_score or 0),

                "training_score":
                    float(training_score or 0),

                "final_score":
                    float(final_score or 0),

                "rating": rating,

                "recommendation": recommendation
            },

            "performance_trend":
                performance_trend,

            "attendance": {

                "present": present,

                "absent": absent,

                "leave": leave,

                "total_days": total_days,

                "percentage":
                    round(attendance_percentage, 2)
            },

            "kra": {

                "total": total_kra,

                "completed":
                    completed_kra,

                "pending":
                    pending_kra,

                "completion_percentage":
                    round(kra_completion, 2)
            },

            "training": {

                "total": total_training,

                "completed":
                    completed_training
            },

            "notifications":
                notifications

        })

    except Exception as e:

        print(
            "EMPLOYEE DASHBOARD ERROR:",
            e
        )

        return jsonify({

            "success": False,

            "message":
                "Unable to load employee dashboard.",

            "error":
                str(e)

        }), 500

    finally:

        if connection:
            connection.close()

# ============================================================
# MANAGER DASHBOARD API
# ============================================================
@dashboard_bp.route("/manager", methods=["GET"])
def manager_dashboard():

    if "user_id" not in session:
        return jsonify({
            "success": False,
            "message": "Login required."
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

        # ====================================================
        # 1. GET LOGGED-IN MANAGER
        # ====================================================

        cursor.execute("""
            SELECT
                e.employee_id,
                e.employee_code,
                e.first_name,
                e.last_name,
                e.email,
                d.department_name,
                des.designation_name,
                b.branch_name
            FROM employees e

            LEFT JOIN departments d
                ON e.department_id = d.department_id

            LEFT JOIN designations des
                ON e.designation_id = des.designation_id

            LEFT JOIN branches b
                ON e.branch_id = b.branch_id

            WHERE e.user_id = %s
        """, (user_id,))

        manager = cursor.fetchone()

        if manager is None:
            return jsonify({
                "success": False,
                "message": "Manager employee record not found."
            }), 404

        manager_id = manager[0]

        manager_name = (
            f"{manager[2] or ''} {manager[3] or ''}"
        ).strip()


        # ====================================================
        # 2. GET MANAGER'S TEAM
        # ====================================================

        cursor.execute("""
            SELECT
                e.employee_id,
                e.employee_code,
                e.first_name,
                e.last_name,
                e.email,
                d.department_name,
                des.designation_name
            FROM employees e

            LEFT JOIN departments d
                ON e.department_id = d.department_id

            LEFT JOIN designations des
                ON e.designation_id = des.designation_id

            WHERE e.manager_id = %s

            ORDER BY e.first_name, e.last_name
        """, (manager_id,))

        team_rows = cursor.fetchall()

        total_employees = len(team_rows)


        # ====================================================
        # 3. TEAM PERFORMANCE
        # ====================================================

        cursor.execute("""
            SELECT
                COALESCE(AVG(pr.final_score), 0)
            FROM performance_result pr

            JOIN employees e
                ON pr.employee_id = e.employee_id

            WHERE e.manager_id = %s
        """, (manager_id,))

        team_average = cursor.fetchone()[0] or 0

        team_average = float(team_average)


        # ====================================================
        # 4. PENDING APPRAISALS
        # ====================================================

        cursor.execute("""
            SELECT COUNT(*)
            FROM manager_appraisal ma

            JOIN employees e
                ON ma.employee_id = e.employee_id

            WHERE e.manager_id = %s
              AND ma.status IN (
                  'Pending',
                  'Submitted'
              )
        """, (manager_id,))

        pending_reviews = cursor.fetchone()[0] or 0


        # ====================================================
        # 5. COMPLETED APPRAISALS
        # ====================================================

        cursor.execute("""
            SELECT COUNT(*)
            FROM manager_appraisal ma

            JOIN employees e
                ON ma.employee_id = e.employee_id

            WHERE e.manager_id = %s
              AND ma.status = 'Approved'
        """, (manager_id,))

        completed_reviews = cursor.fetchone()[0] or 0


        # ====================================================
        # 6. TEAM ATTENDANCE
        # ====================================================

        cursor.execute("""
            SELECT
                COUNT(*) FILTER (
                    WHERE a.status = 'Present'
                ),

                COUNT(*) FILTER (
                    WHERE a.status = 'Absent'
                ),

                COUNT(*) FILTER (
                    WHERE a.status = 'Leave'
                ),

                COUNT(*)

            FROM attendance a

            JOIN employees e
                ON a.employee_id = e.employee_id

            WHERE e.manager_id = %s
        """, (manager_id,))

        attendance = cursor.fetchone()

        present = attendance[0] or 0
        absent = attendance[1] or 0
        leave = attendance[2] or 0
        total_attendance = attendance[3] or 0


        attendance_percentage = 0

        if total_attendance > 0:

            attendance_percentage = (
                present /
                total_attendance
            ) * 100


        # ====================================================
        # 7. KRA SUMMARY
        # ====================================================

        cursor.execute("""
            SELECT
                COUNT(*),

                COUNT(*) FILTER (
                    WHERE ek.status = 'Completed'
                )

            FROM employee_kra ek

            JOIN employees e
                ON ek.employee_id = e.employee_id

            WHERE e.manager_id = %s
        """, (manager_id,))

        kra = cursor.fetchone()

        total_kras = kra[0] or 0
        completed_kras = kra[1] or 0
        pending_kras = total_kras - completed_kras


        kra_percentage = 0

        if total_kras > 0:

            kra_percentage = (
                completed_kras /
                total_kras
            ) * 100


        # ====================================================
        # 8. EMPLOYEE PERFORMANCE LIST
        # ====================================================

        cursor.execute("""
            SELECT
                e.employee_id,
                e.employee_code,
                e.first_name,
                e.last_name,

                COALESCE(
                    pr.final_score,
                    0
                ) AS final_score,

                COALESCE(
                    pr.rating,
                    'Not Available'
                ) AS rating

            FROM employees e

            LEFT JOIN LATERAL (

                SELECT
                    final_score,
                    rating

                FROM performance_result

                WHERE employee_id = e.employee_id

                ORDER BY
                    appraisal_year DESC,
                    performance_id DESC

                LIMIT 1

            ) pr ON TRUE

            WHERE e.manager_id = %s

            ORDER BY
                final_score DESC
        """, (manager_id,))

        performance_rows = cursor.fetchall()

        team_performance = []

        for row in performance_rows:

            team_performance.append({

                "employee_id": row[0],

                "employee_code": row[1],

                "name":
                    f"{row[2] or ''} {row[3] or ''}".strip(),

                "score":
                    float(row[4] or 0),

                "rating":
                    row[5]
            })


        # ====================================================
        # 9. PERFORMANCE DISTRIBUTION
        # ====================================================

        outstanding = 0
        excellent = 0
        very_good = 0
        average = 0
        needs_improvement = 0


        for employee in team_performance:

            score = employee["score"]

            if score >= 90:

                outstanding += 1

            elif score >= 80:

                excellent += 1

            elif score >= 70:

                very_good += 1

            elif score >= 50:

                average += 1

            else:

                needs_improvement += 1


        # ====================================================
        # 10. COMPETENCY AVERAGES
        # ====================================================

        cursor.execute("""
            SELECT
                COALESCE(AVG(ma.productivity), 0),
                COALESCE(AVG(ma.quality_of_work), 0),
                COALESCE(AVG(ma.teamwork), 0),
                COALESCE(AVG(ma.communication), 0),
                COALESCE(AVG(ma.problem_solving), 0),
                COALESCE(AVG(ma.initiative), 0)

            FROM manager_appraisal ma

            JOIN employees e
                ON ma.employee_id = e.employee_id

            WHERE e.manager_id = %s
        """, (manager_id,))

        competency = cursor.fetchone()


        competencies = {

            "productivity":
                round(float(competency[0] or 0) * 20, 2),

            "quality_of_work":
                round(float(competency[1] or 0) * 20, 2),

            "teamwork":
                round(float(competency[2] or 0) * 20, 2),

            "communication":
                round(float(competency[3] or 0) * 20, 2),

            "problem_solving":
                round(float(competency[4] or 0) * 20, 2),

            "initiative":
                round(float(competency[5] or 0) * 20, 2)
        }
        # ====================================================
        # 11. RECENT APPRAISAL ACTIVITY
        # ====================================================

        cursor.execute("""
            SELECT
                ma.appraisal_id,
                e.employee_code,
                e.first_name,
                e.last_name,
                ma.appraisal_cycle,
                ma.status,
                ma.appraisal_date

            FROM manager_appraisal ma

            JOIN employees e
                ON ma.employee_id = e.employee_id

            WHERE e.manager_id = %s

            ORDER BY ma.created_at DESC

            LIMIT 10
        """, (manager_id,))

        activity_rows = cursor.fetchall()

        recent_activities = []

        for row in activity_rows:
            recent_activities.append({

                "appraisal_id":
                    row[0],

                "employee_code":
                    row[1],

                "employee_name":
                    f"{row[2] or ''} {row[3] or ''}".strip(),

                "appraisal_cycle":
                    row[4],

                "status":
                    row[5],

                "appraisal_date":
                    row[6].isoformat()
                    if row[6]
                    else None
            })
        # ====================================================
        # 11. TEAM APPRAISAL REVIEWS
        # ====================================================

        cursor.execute("""
            SELECT
                ma.appraisal_id,
                e.employee_id,
                e.employee_code,
                e.first_name,
                e.last_name,
                d.department_name,
                ma.appraisal_cycle,
                ma.status,
                ma.appraisal_date,

                COALESCE(pr.self_appraisal_score, 0) AS self_score,
                COALESCE(pr.manager_score, 0) AS manager_score,
                COALESCE(pr.final_score, 0) AS final_score,
                COALESCE(pr.rating, 'Not Available') AS rating

            FROM manager_appraisal ma

            JOIN employees e
                ON ma.employee_id = e.employee_id

            LEFT JOIN departments d
                ON e.department_id = d.department_id

            LEFT JOIN LATERAL (
                SELECT
                    self_appraisal_score,
                    manager_score,
                    final_score,
                    rating
                FROM performance_result pr2

                WHERE pr2.employee_id = e.employee_id

                ORDER BY
                    pr2.appraisal_year DESC,
                    pr2.performance_id DESC

                LIMIT 1
            ) pr
                ON TRUE

            WHERE ma.manager_id = %s

            ORDER BY
                ma.created_at DESC

            LIMIT 10
        """, (manager_id,))

        review_rows = cursor.fetchall()

        appraisal_reviews = []

        for row in review_rows:
            appraisal_reviews.append({

                "appraisal_id": row[0],

                "employee_id": row[1],

                "employee_code": row[2],

                "employee_name":
                    f"{row[3] or ''} {row[4] or ''}".strip(),

                "department":
                    row[5] or "Not Assigned",

                "appraisal_cycle":
                    row[6],

                "status":
                    row[7],

                "appraisal_date":
                    row[8].isoformat()
                    if row[8]
                    else None,

                # performance_result stores these as percentages
                # Convert them to a 5-point scale for the UI

                "self_score":
                    round(float(row[9] or 0) / 20, 2),

                "manager_score":
                    round(float(row[10] or 0) / 20, 2),

                "final_score":
                    round(float(row[11] or 0), 2),

                "rating":
                    row[12] or "Not Available"
            })


        # ====================================================
        # 12. RETURN RESPONSE
        # ====================================================

        return jsonify({

            "success": True,

            "manager": {

                "id": manager_id,

                "employee_code":
                    manager[1],

                "name":
                    manager_name,

                "email":
                    manager[4],

                "department":
                    manager[5] or "Not Assigned",

                "designation":
                    manager[6] or "Manager",

                "branch":
                    manager[7] or "Not Assigned"
            },


            "summary": {

                "total_employees":
                    total_employees,

                "team_average":
                    round(team_average, 2),

                "pending_reviews":
                    pending_reviews,

                "completed_reviews":
                    completed_reviews,

                "attendance_percentage":
                    round(attendance_percentage, 2),

                "total_kras":
                    total_kras,

                "completed_kras":
                    completed_kras,

                "pending_kras":
                    pending_kras,

                "kra_completion_percentage":
                    round(kra_percentage, 2)
            },


            "attendance": {

                "present":
                    present,

                "absent":
                    absent,

                "leave":
                    leave,

                "total":
                    total_attendance,

                "percentage":
                    round(attendance_percentage, 2)
            },


            "performance_distribution": {

                "outstanding":
                    outstanding,

                "excellent":
                    excellent,

                "very_good":
                    very_good,

                "average":
                    average,

                "needs_improvement":
                    needs_improvement
            },


            "competencies":
                competencies,

            "team_performance":
                team_performance,

            "recent_activities":
                recent_activities,

            "appraisal_reviews":
                appraisal_reviews
        })


    except Exception as e:

        print(
            "Manager dashboard error:",
            e
        )

        return jsonify({

            "success": False,

            "message":
                "Failed to load manager dashboard.",

            "error":
                str(e)

        }), 500


    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()
# ============================================================
# MANAGER - TEAM EVALUATION DATA
# ============================================================

@dashboard_bp.route("/api/manager/team-evaluations", methods=["GET"])
def manager_team_evaluations():

    if "user_id" not in session:
        return jsonify({
            "success": False,
            "message": "Login required."
        }), 401

    if session.get("role_name", "").lower() != "manager":
        return jsonify({
            "success": False,
            "message": "Manager access required."
        }), 403

    connection = None

    try:

        connection = get_db_connection()
        cursor = connection.cursor()

        # ----------------------------------------------------
        # Get logged-in manager
        # ----------------------------------------------------

        cursor.execute("""
            SELECT employee_id
            FROM employees
            WHERE user_id = %s
        """, (session["user_id"],))

        manager = cursor.fetchone()

        if not manager:
            return jsonify({
                "success": False,
                "message": "Manager record not found."
            }), 404

        manager_id = manager[0]

        # ----------------------------------------------------
        # Get manager's team and appraisal records
        # ----------------------------------------------------

        cursor.execute("""
            SELECT
                ma.appraisal_id,
                e.employee_id,
                e.employee_code,
                e.first_name,
                e.last_name,
                d.department_name,
                des.designation_name,
                ma.appraisal_cycle,
                ma.status,
                ma.appraisal_date,

                COALESCE(pr.self_appraisal_score, 0),
                COALESCE(pr.manager_score, 0),
                COALESCE(pr.behaviour_score, 0),
                COALESCE(pr.final_score, 0),
                COALESCE(pr.rating, 'Not Available'),

                ma.productivity,
                ma.quality_of_work,
                ma.teamwork,
                ma.communication,
                ma.problem_solving,
                ma.initiative

            FROM manager_appraisal ma

            JOIN employees e
                ON ma.employee_id = e.employee_id

            LEFT JOIN departments d
                ON e.department_id = d.department_id

            LEFT JOIN designations des
                ON e.designation_id = des.designation_id

            LEFT JOIN LATERAL (
                SELECT
                    self_appraisal_score,
                    manager_score,
                    behaviour_score,
                    final_score,
                    rating
                FROM performance_result
                WHERE employee_id = e.employee_id
                ORDER BY
                    appraisal_year DESC,
                    performance_id DESC
                LIMIT 1
            ) pr ON TRUE

            WHERE e.manager_id = %s

            ORDER BY ma.created_at DESC
        """, (manager_id,))

        rows = cursor.fetchall()

        evaluations = []

        for row in rows:

            evaluations.append({

                "appraisal_id": row[0],

                "employee_id": row[1],

                "employee_code": row[2],

                "employee_name":
                    f"{row[3] or ''} {row[4] or ''}".strip(),

                "department":
                    row[5] or "Not Assigned",

                "designation":
                    row[6] or "Not Assigned",

                "appraisal_cycle":
                    row[7],

                "status":
                    row[8],

                "appraisal_date":
                    row[9].isoformat()
                    if row[9]
                    else None,

                "self_score":
                    round(float(row[10] or 0) / 20, 2),

                "manager_score":
                    round(float(row[11] or 0) / 20, 2),

                "behaviour_score":
                    round(float(row[12] or 0) / 20, 2),

                "final_score":
                    round(float(row[13] or 0), 2),

                "rating":
                    row[14],

                "competencies": {

                    "productivity":
                        float(row[15] or 0),

                    "quality_of_work":
                        float(row[16] or 0),

                    "teamwork":
                        float(row[17] or 0),

                    "communication":
                        float(row[18] or 0),

                    "problem_solving":
                        float(row[19] or 0),

                    "initiative":
                        float(row[20] or 0)
                }
            })

        cursor.close()

        return jsonify({
            "success": True,
            "evaluations": evaluations
        })

    except Exception as e:

        print(
            "Team evaluation API error:",
            e
        )

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

    finally:

        if connection:
            connection.close()

# ============================================================
# SAVE MANAGER TEAM EVALUATION
# ============================================================

@dashboard_bp.route(
    "/api/manager/team-evaluations/<int:appraisal_id>",
    methods=["POST"]
)
def save_team_evaluation(appraisal_id):

    if "user_id" not in session:
        return jsonify({
            "success": False,
            "message": "Login required."
        }), 401

    if session.get("role_name", "").lower() != "manager":
        return jsonify({
            "success": False,
            "message": "Manager access required."
        }), 403

    connection = None

    try:

        data = request.get_json()

        if not data:
            return jsonify({
                "success": False,
                "message": "No evaluation data received."
            }), 400

        performance_score = float(
            data.get("performance_score", 0)
        )

        behaviour_score = float(
            data.get("behaviour_score", 0)
        )

        remarks = (
            data.get("remarks") or ""
        ).strip()

        # --------------------------------------------
        # Validate scores
        # --------------------------------------------

        if not 1 <= performance_score <= 5:
            return jsonify({
                "success": False,
                "message":
                    "Performance score must be between 1 and 5."
            }), 400

        if not 1 <= behaviour_score <= 5:
            return jsonify({
                "success": False,
                "message":
                    "Behaviour score must be between 1 and 5."
            }), 400

        connection = get_db_connection()
        cursor = connection.cursor()

        # --------------------------------------------
        # Find logged-in manager
        # --------------------------------------------

        cursor.execute("""
            SELECT employee_id
            FROM employees
            WHERE user_id = %s
        """, (session["user_id"],))

        manager = cursor.fetchone()

        if not manager:
            return jsonify({
                "success": False,
                "message": "Manager record not found."
            }), 404

        manager_id = manager[0]

        # --------------------------------------------
        # Make sure appraisal belongs to this manager
        # --------------------------------------------

        cursor.execute("""
            SELECT appraisal_id
            FROM manager_appraisal
            WHERE appraisal_id = %s
              AND manager_id = %s
        """, (
            appraisal_id,
            manager_id
        ))

        appraisal = cursor.fetchone()

        if not appraisal:
            return jsonify({
                "success": False,
                "message":
                    "This appraisal does not belong to you."
            }), 403

        # --------------------------------------------
        # Convert 1-5 scores into the same scale used
        # by manager_appraisal competency fields.
        #
        # 4.5 / 5 -> 4.5
        #
        # The dashboard later converts these values
        # to percentages by multiplying by 20.
        # --------------------------------------------

        cursor.execute("""
            UPDATE manager_appraisal
            SET
                productivity = %s,
                behaviour_score = %s,
                remarks = %s,
                status = 'Submitted',
                appraisal_date = CURRENT_DATE
            WHERE appraisal_id = %s
              AND manager_id = %s
        """, (
            performance_score,
            behaviour_score,
            remarks,
            appraisal_id,
            manager_id
        ))

        connection.commit()

        cursor.close()

        return jsonify({
            "success": True,
            "message":
                "Evaluation submitted successfully."
        })

    except Exception as e:

        if connection:
            connection.rollback()

        print(
            "Save team evaluation error:",
            e
        )

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

    finally:

        if connection:
            connection.close()

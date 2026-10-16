import os
from datetime import date, datetime
from flask import (
    Blueprint,
    jsonify,
    session,
    render_template,
    redirect,
    url_for,
    request,
    flash,
    send_from_directory
)
from werkzeug.utils import secure_filename

from config import get_db_connection
# ============================================================
# KPI / GOAL ACHIEVEMENT SCORE CALCULATION
# ============================================================

def calculate_kpi_score(cursor, employee_id, cycle_id):
    """
    Calculate the overall KPI / Goal Achievement score
    for an employee for the selected appraisal cycle.

    Individual KPI formula:
        KPI Score = MIN((Achieved Value / Assigned Target) * 100, 100)

    Overall KPI score:
        Average of all individual KPI scores.
    """

    cursor.execute("""
        SELECT
            ek.employee_kpi_id,
            ek.kpi_id,
            ek.assigned_target,
            COALESCE(latest_record.achieved_value, 0) AS achieved_value

        FROM employee_kpi ek

        LEFT JOIN LATERAL (
            SELECT
                kr.achieved_value
            FROM kpi_records kr
            WHERE kr.employee_id = ek.employee_id
              AND kr.kpi_id = ek.kpi_id
              AND kr.evaluation_month >= DATE_TRUNC('month', ek.start_date)
              AND kr.evaluation_month <= DATE_TRUNC('month', ek.end_date)
            ORDER BY kr.evaluation_month DESC, kr.created_at DESC
            LIMIT 1
        ) latest_record ON TRUE

        WHERE ek.employee_id = %s
          AND ek.cycle_id = %s

        ORDER BY
            ek.employee_kpi_id
    """, (
        employee_id,
        cycle_id
    ))

    kpi_rows = cursor.fetchall()

    if not kpi_rows:
        return 0

    kpi_scores = []

    for row in kpi_rows:

        assigned_target = row[2]
        achieved_value = row[3]

        # Ignore assignments without a valid target
        if assigned_target is None:
            continue

        if float(assigned_target) <= 0:
            continue

        # Calculate individual KPI percentage
        score = (
            float(achieved_value)
            / float(assigned_target)
        ) * 100

        # Maximum individual KPI score is 100
        score = min(score, 100)

        kpi_scores.append(score)

    if not kpi_scores:
        return 0

    # Average of all individual KPI scores
    overall_kpi_score = (
        sum(kpi_scores)
        / len(kpi_scores)
    )

    return round(
        overall_kpi_score,
        2
    )

def calculate_training_score(cursor, employee_id):
    """
    Calculate the employee's training score based on session-wise attendance.
    Sessions marked as 'Approved Leave' are excluded from the denominator.
    If the employee has no training assigned or no qualifying attendance marked ('Attended' or 'Absent'),
    returns None so that the 5% training weight is excluded and remaining weights normalized.
    """
    cursor.execute("""
        SELECT
            COUNT(*) FILTER (WHERE ta.attendance_status = 'Attended') AS attended,
            COUNT(*) FILTER (WHERE ta.attendance_status IN ('Attended', 'Absent')) AS evaluated
        FROM training_records tr
        LEFT JOIN training_sessions ts
            ON ts.program_id = tr.program_id
        LEFT JOIN training_attendance ta
            ON ta.session_id = ts.session_id
           AND ta.employee_id = tr.employee_id
        WHERE tr.employee_id = %s
    """, (employee_id,))

    row = cursor.fetchone()
    if not row:
        return None

    attended, evaluated = row[0] or 0, row[1] or 0
    if evaluated == 0:
        return None

    return round((attended / evaluated) * 100.0, 2)


def _safe_insert_notification(cursor, user_id, title, message, notification_type="system"):
    """
    Insert a notification if an identical unread notification does not already exist for the user.
    """
    if not user_id:
        return
    cursor.execute("""
        SELECT notification_id FROM notifications
        WHERE user_id = %s AND title = %s AND message = %s AND is_read = FALSE
    """, (user_id, title, message))
    if cursor.fetchone():
        return
    cursor.execute("""
        INSERT INTO notifications (user_id, title, message, notification_type, is_read, created_at)
        VALUES (%s, %s, %s, %s, FALSE, NOW())
    """, (user_id, title, message, notification_type))


# ============================================================
# CANONICAL FINAL PERFORMANCE CALCULATION
# ============================================================

def update_final_performance_score(cursor, employee_id, cycle_id):
    """
    Calculate and persist the final performance score ONLY when all required
    components are available (prevents premature low scores).

    Weights:
        KPI: 40%
        Manager Appraisal: 30%
        Attendance: 10%
        Behaviour Assessment: 10%
        Self-Appraisal: 5%
        Training: 5% (optional; weight redistributed if not enrolled in training)
    """
    cursor.execute("""
        SELECT
            kpi_score,
            manager_score,
            attendance_score,
            behaviour_score,
            self_appraisal_score,
            training_score
        FROM performance_result
        WHERE employee_id = %s
          AND cycle_id = %s
    """, (employee_id, cycle_id))

    row = cursor.fetchone()
    if not row:
        return None

    kpi_score, manager_score, attendance_score, behaviour_score, self_score, training_score = row

    # Check if all required components are completed
    required_components = [kpi_score, manager_score, attendance_score, behaviour_score, self_score]
    if any(score is None for score in required_components):
        # Components still pending - do not prematurely finalize
        return None

    weights = {
        "kpi": 0.40,
        "manager": 0.30,
        "attendance": 0.10,
        "behaviour": 0.10,
        "self": 0.05
    }
    scores = {
        "kpi": float(kpi_score),
        "manager": float(manager_score),
        "attendance": float(attendance_score),
        "behaviour": float(behaviour_score),
        "self": float(self_score)
    }

    if training_score is not None:
        weights["training"] = 0.05
        scores["training"] = float(training_score)

    total_weight = sum(weights.values())
    final_score = round(sum(scores[k] * weights[k] for k in scores) / total_weight, 2)

    if final_score >= 90.0:
        rating = "Outstanding"
    elif final_score >= 80.0:
        rating = "Excellent"
    elif final_score >= 70.0:
        rating = "Good"
    elif final_score >= 60.0:
        rating = "Needs Improvement"
    else:
        rating = "Unsatisfactory"

    if final_score >= 90.0:
        recommendation = "Promotion Recommended and Salary Increment Recommended"
    elif final_score >= 85.0:
        recommendation = "Salary Increment Recommended"
    elif final_score >= 75.0:
        recommendation = "No Immediate Action"
    else:
        recommendation = "Training / Development Recommended"

    cursor.execute("""
        UPDATE performance_result
        SET
            final_score = %s,
            rating = %s,
            recommendation = %s
        WHERE employee_id = %s
          AND cycle_id = %s
    """, (
        final_score,
        rating,
        recommendation,
        employee_id,
        cycle_id
    ))
    return final_score


dashboard_bp = Blueprint(
    "dashboard",
    __name__
)


# Page-to-role mapping for the screens that are currently presentation-led.
# Keeping the mapping explicit prevents arbitrary templates being rendered from
# a URL while allowing the existing .html navigation links to keep working.
ADDITIONAL_PAGES = {
    "appraisal-form": ("appraisal_form.html", {"employee", "manager"}),
    "appraisal_form.html": ("appraisal_form.html", {"employee", "manager"}),
    "employee-training": ("employee_training.html", {"employee", "manager"}),
    "employee_training.html": ("employee_training.html", {"employee", "manager"}),
    "leave-request": ("leave_request.html", {"employee", "manager"}),
    "leave_request.html": ("leave_request.html", {"employee", "manager"}),
    "my-appraisals": ("my_appraisals.html", {"employee", "manager"}),
    "my_appraisals.html": ("my_appraisals.html", {"employee", "manager"}),
    "employee-goals": ("employee_goals.html", {"employee", "manager"}),
    "employee_goals.html": ("employee_goals.html", {"employee", "manager"}),
    "employee-attendance": ("employee_attendance.html", {"employee", "manager"}),
    "employee_attendance.html": ("employee_attendance.html", {"employee", "manager"}),
    "self-appraisal": ("self_appraisal.html", {"employee", "manager"}),
    "self_appraisal.html": ("self_appraisal.html", {"employee", "manager"}),
    "feedback-360": ("feedback_360.html", {"manager", "hr", "admin"}),
    "feedback_360.html": ("feedback_360.html", {"manager", "hr", "admin"}),
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
    "kra-kpi-report-old": ("kra_kpi_report.html", {"hr", "admin"}),
    "kra_kpi_report.html": ("kra_kpi_report.html", {"hr", "admin"}),
    "profile": ("profile.html", {"employee", "manager", "hr", "admin"}),
    "profile.html": ("profile.html", {"employee", "manager", "hr", "admin"}),
    "employee_dashboard.html": ("employee_dashboard.html", {"employee"}),
    "manager_dashboard.html": ("manager_dashboard.html", {"manager"}),
    "team_evaluation.html": ("team_evaluation.html", {"manager"}),
    "review_appraisal.html": ("review_appraisal.html", {"manager"}),
    "manager-appraisal": ("review_appraisal.html", {"manager"}),
    "manager_appraisal.html": ("review_appraisal.html", {"manager"}),
    "admin-dashboard": ("hr_dashboard.html", {"admin", "hr"}),
    "admin_dashboard.html": ("hr_dashboard.html", {"admin", "hr"}),
    "login.html": ("login.html", None),
}


def _normalize_role(role_name):
    r = (role_name or "").lower().strip()
    if "human" in r or "hr" in r:
        return "hr"
    if "manager" in r:
        return "manager"
    if "admin" in r:
        return "admin"
    if "employee" in r:
        return "employee"
    return r


def _render_additional_page(template_name, allowed_roles):
    if allowed_roles is None:
        return render_template(template_name)

    if "user_id" not in session:
        return redirect(url_for("login_page"))

    user_role = _normalize_role(session.get("role_name", ""))
    raw_role = session.get("role_name", "").lower().strip()

    user_roles = {user_role, raw_role}
    if "admin" in raw_role:
        user_roles.add("admin")
    if "hr" in raw_role or "human" in raw_role:
        user_roles.add("hr")
    if "manager" in raw_role:
        user_roles.add("manager")
    if "employee" in raw_role:
        user_roles.add("employee")

    if not (user_roles & allowed_roles):
        return "Access Denied", 403

    return render_template(template_name)

# ============================================================
# EMPLOYEE ATTENDANCE PAGE
# ============================================================

def calculate_attendance_percentage(present_days, working_days, half_days=0):
    """Return attendance percentage, treating each half day as 0.5 present day."""
    if working_days <= 0:
        return 0

    attended_days = present_days + (half_days * 0.5)
    return (attended_days / working_days) * 100


def calculate_attendance_score(present_days, working_days, half_days=0):
    if working_days <= 0:
        return 0

    percentage = calculate_attendance_percentage(
        present_days,
        working_days,
        half_days
    )

    if percentage >= 90:
        return 5
    elif percentage >= 85:
        return 4
    elif percentage >= 80:
        return 3
    elif percentage >= 75:
        return 2
    else:
        return 1


# ============================================================
# LEAVE CATEGORIES & BALANCE HELPERS
# ============================================================

LEAVE_CATEGORIES = (
    {
        "name": "Casual Leave",
        "code": "CL",
        "total_days": 0,
        "icon": "bi-calendar-check",
        "icon_class": "red-icon",
    },
    {
        "name": "Sick Leave",
        "code": "SL",
        "total_days": 0,
        "icon": "bi-hospital",
        "icon_class": "gold-icon",
    },
    {
        "name": "Annual Privilege Leave",
        "code": "PL",
        "total_days": 0,
        "icon": "bi-airplane",
        "icon_class": "red-icon",
    },
)


def normalize_leave_type(leave_type):
    return str(leave_type or "").strip().casefold()


def get_leave_category(leave_type):
    normalized_leave_type = normalize_leave_type(leave_type)

    return next(
        (
            category
            for category in LEAVE_CATEGORIES
            if normalize_leave_type(category["name"])
            == normalized_leave_type
        ),
        None
    )


class LeaveBalancesList(list):
    @property
    def casual(self):
        item = next((b for b in self if b.get("code") == "CL"), {})
        limit = item.get("total_days", 0)
        used = item.get("used_days", 0)
        pending = item.get("pending_days", 0)
        return {"limit": limit, "used": used, "pending": pending, "available": item.get("remaining_days", max(0, limit - used - pending))}

    @property
    def sick(self):
        item = next((b for b in self if b.get("code") == "SL"), {})
        limit = item.get("total_days", 0)
        used = item.get("used_days", 0)
        pending = item.get("pending_days", 0)
        return {"limit": limit, "used": used, "pending": pending, "available": item.get("remaining_days", max(0, limit - used - pending))}

    @property
    def privileged(self):
        item = next((b for b in self if b.get("code") == "PL"), {})
        limit = item.get("total_days", 0)
        used = item.get("used_days", 0)
        pending = item.get("pending_days", 0)
        return {"limit": limit, "used": used, "pending": pending, "available": item.get("remaining_days", max(0, limit - used - pending))}


def calculate_leave_balances(approved_days_by_type, department_totals=None, pending_days_by_type=None):
    """Calculate balances from department totals and approved leave usage."""
    department_totals = department_totals or {}
    pending_days_by_type = pending_days_by_type or {}
    balances = []

    for category in LEAVE_CATEGORIES:
        category_name = normalize_leave_type(category["name"])
        total_days = int(department_totals.get(category_name, 0) or 0)
        used_days = int(
            approved_days_by_type.get(
                category_name,
                0
            ) or 0
        )
        pending_days = int(
            pending_days_by_type.get(
                category_name,
                0
            ) or 0
        )

        balances.append({
            **category,
            "total_days": total_days,
            "used_days": used_days,
            "pending_days": pending_days,
            "remaining_days": max(total_days - used_days - pending_days, 0),
        })

    return LeaveBalancesList(balances)


def get_employee_leave_balances(cursor, employee_id):
    cursor.execute("""
        SELECT
            COALESCE(d.casual_leave_limit, 0),
            COALESCE(d.sick_leave_limit, 0),
            COALESCE(d.privileged_leave_limit, 0)
        FROM employees e
        JOIN departments d ON d.department_id = e.department_id
        WHERE e.employee_id = %s
    """, (employee_id,))

    total_row = cursor.fetchone() or (0, 0, 0)
    department_totals = {
        normalize_leave_type(category["name"]): (total_days or 0)
        for category, total_days in zip(LEAVE_CATEGORIES, total_row)
    }

    cursor.execute("""
        SELECT
            LOWER(TRIM(leave_type)) AS leave_type,
            LOWER(TRIM(status)) AS status,
            COALESCE(SUM(number_of_days), 0) AS days
        FROM leave_requests
        WHERE employee_id = %s
          AND LOWER(TRIM(status)) IN ('approved', 'pending')
        GROUP BY LOWER(TRIM(leave_type)), LOWER(TRIM(status))
    """, (employee_id,))

    approved_days_by_type = {}
    pending_days_by_type = {}
    for l_type, l_status, l_days in cursor.fetchall():
        if l_status == 'approved':
            approved_days_by_type[l_type] = approved_days_by_type.get(l_type, 0) + l_days
        elif l_status == 'pending':
            pending_days_by_type[l_type] = pending_days_by_type.get(l_type, 0) + l_days

    return calculate_leave_balances(
        approved_days_by_type,
        department_totals,
        pending_days_by_type
    )


@dashboard_bp.route("/employee_attendance.html")
@dashboard_bp.route("/employee-attendance")
def employee_attendance_page():

    # --------------------------------------------------------
    # LOGIN CHECK
    # --------------------------------------------------------
    if "user_id" not in session:
        return redirect(url_for("login_page"))

    # --------------------------------------------------------
    # EMPLOYEE & MANAGER SELF-SERVICE ACCESS
    # --------------------------------------------------------
    role = session.get("role_name", "")

    if _normalize_role(role) not in ["employee", "manager"]:
        return "Access Denied", 403

    user_id = session["user_id"]

    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # ----------------------------------------------------
        # GET LOGGED-IN EMPLOYEE
        # ----------------------------------------------------
        cursor.execute("""
            SELECT
                employee_id,
                employee_code,
                first_name,
                last_name
            FROM employees
            WHERE user_id = %s
        """, (user_id,))

        employee = cursor.fetchone()
        if not employee and session.get("employee_id"):
            cursor.execute("""
                SELECT
                    employee_id,
                    employee_code,
                    first_name,
                    last_name
                FROM employees
                WHERE employee_id = %s
            """, (session.get("employee_id"),))
            employee = cursor.fetchone()

        if not employee:
            return "Employee profile not found.", 404

        employee_id = employee[0]

        employee_data = {
            "employee_id": employee[0],
            "employee_code": employee[1],
            "first_name": employee[2] or "",
            "last_name": employee[3] or "",
            "name": f"{employee[2] or ''} {employee[3] or ''}".strip()
        }

        # ----------------------------------------------------
        # GET AVAILABLE ATTENDANCE MONTHS
        # ----------------------------------------------------
        cursor.execute("""
            SELECT DISTINCT
                EXTRACT(YEAR FROM attendance_date)::INTEGER AS year,
                EXTRACT(MONTH FROM attendance_date)::INTEGER AS month
            FROM attendance
            WHERE employee_id = %s
            ORDER BY year DESC, month DESC
        """, (employee_id,))

        period_rows = cursor.fetchall()

        period_options = []

        for year, month in period_rows:
            period_options.append({
                "value": f"{year:04d}-{month:02d}",
                "label": date(year, month, 1).strftime("%B %Y"),
                "year": year,
                "month": month
            })

        # ----------------------------------------------------
        # SELECT MONTH
        # ----------------------------------------------------
        requested_period = request.args.get("period")

        selected_period = None

        if requested_period:
            try:
                year, month = map(
                    int,
                    requested_period.split("-")
                )

                if 1 <= month <= 12:
                    selected_period = {
                        "value": f"{year:04d}-{month:02d}",
                        "label": date(
                            year,
                            month,
                            1
                        ).strftime("%B %Y"),
                        "year": year,
                        "month": month
                    }

            except (ValueError, TypeError):
                selected_period = None

        # If no valid period was selected,
        # use the latest available month.
        if selected_period is None:

            if period_options:
                selected_period = period_options[0]

            else:
                today = date.today()

                selected_period = {
                    "value": today.strftime("%Y-%m"),
                    "label": today.strftime("%B %Y"),
                    "year": today.year,
                    "month": today.month
                }

        # ----------------------------------------------------
        # MONTH START / END
        # ----------------------------------------------------
        period_start = date(
            selected_period["year"],
            selected_period["month"],
            1
        )

        if selected_period["month"] == 12:
            period_end = date(
                selected_period["year"] + 1,
                1,
                1
            )
        else:
            period_end = date(
                selected_period["year"],
                selected_period["month"] + 1,
                1
            )

        # ----------------------------------------------------
        # ATTENDANCE SUMMARY
        # Excludes weekly offs and holidays dynamically from status.
        # ----------------------------------------------------
        cursor.execute("""
            SELECT
                COUNT(*) FILTER (
                    WHERE LOWER(TRIM(a.status)) NOT IN ('weekly off', 'holiday')
                ) AS total_days,

                COUNT(*) FILTER (
                    WHERE LOWER(TRIM(a.status)) = 'present'
                ) AS present_days,

                COUNT(*) FILTER (
                    WHERE LOWER(TRIM(a.status)) = 'absent'
                ) AS absent_days,

                COUNT(*) FILTER (
                    WHERE LOWER(TRIM(a.status)) = 'leave'
                ) AS leave_days,

                COUNT(*) FILTER (
                    WHERE LOWER(TRIM(a.status))
                    IN ('half day', 'half-day')
                ) AS half_days

            FROM attendance a

            WHERE a.employee_id = %s

              AND a.attendance_date >= %s
              AND a.attendance_date < %s
        """, (
            employee_id,
            period_start,
            period_end
        ))

        summary = cursor.fetchone()

        total_days = summary[0] or 0
        present_days = summary[1] or 0
        absent_days = summary[2] or 0
        leave_days = summary[3] or 0
        half_days = summary[4] or 0

        # ----------------------------------------------------
        # ATTENDANCE PERCENTAGE
        # ----------------------------------------------------
        attendance_percentage = round(
            calculate_attendance_percentage(
                present_days,
                total_days,
                half_days
            ),
            1
        )

        # ----------------------------------------------------
        # ATTENDANCE SCORE
        # ----------------------------------------------------
        attendance_score = calculate_attendance_score(
            present_days,
            total_days,
            half_days
        )

        # ----------------------------------------------------
        # DAILY ATTENDANCE RECORDS
        # ----------------------------------------------------
        cursor.execute("""
            SELECT
                a.attendance_date,
                a.status,
                a.check_in,
                a.check_out
            FROM attendance a

            WHERE a.employee_id = %s

              AND a.attendance_date >= %s
              AND a.attendance_date < %s

            ORDER BY a.attendance_date DESC
        """, (
            employee_id,
            period_start,
            period_end
        ))

        attendance_rows = cursor.fetchall()

        attendance_records = []

        for row in attendance_rows:

            attendance_records.append({
                "date": row[0],
                "status": row[1],
                "check_in": row[2],
                "check_out": row[3]
            })

        # ----------------------------------------------------
        # ATTENDANCE DATA FOR TEMPLATE
        # ----------------------------------------------------
        attendance = {
            "percentage": attendance_percentage,
            "score": attendance_score,
            "working_days": total_days,
            "present_days": present_days,
            "absent_days": absent_days,
            "leave_days": leave_days,
            "half_days": half_days,
            "period_value": selected_period["value"],
            "period_label": selected_period["label"]
        }

        return render_template(
            "employee_attendance.html",
            employee=employee_data,
            attendance=attendance,
            attendance_records=attendance_records,
            period_options=period_options
        )

    except Exception as e:

        print(
            "EMPLOYEE ATTENDANCE ERROR:",
            e
        )

        return (
            "Unable to load attendance page.",
            500
        )

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()

# ============================================================
# EMPLOYEE LEAVE REQUEST
# ============================================================

@dashboard_bp.route("/leave_request.html", methods=["GET", "POST"])
@dashboard_bp.route("/leave-request", methods=["GET", "POST"])
def leave_request_page():

    # --------------------------------------------------------
    # LOGIN CHECK
    # --------------------------------------------------------
    if "user_id" not in session:
        return redirect(url_for("login_page"))

    # --------------------------------------------------------
    # EMPLOYEE & MANAGER SELF-SERVICE ACCESS
    # --------------------------------------------------------
    role = session.get("role_name", "")

    if _normalize_role(role) not in ["employee", "manager"]:
        return "Access Denied", 403

    user_id = session["user_id"]

    conn = None
    cursor = None

    try:

        conn = get_db_connection()
        cursor = conn.cursor()

        # ----------------------------------------------------
        # GET LOGGED-IN EMPLOYEE & DEPARTMENT LEAVE LIMITS
        # ----------------------------------------------------
        cursor.execute("""
            SELECT
                e.employee_id,
                e.employee_code,
                e.first_name,
                e.last_name,
                d.department_id,
                d.department_name,
                ds.designation_name,
                COALESCE(d.casual_leave_limit, 0),
                COALESCE(d.sick_leave_limit, 0),
                COALESCE(d.privileged_leave_limit, 0)
            FROM employees e
            LEFT JOIN departments d ON e.department_id = d.department_id
            LEFT JOIN designations ds ON e.designation_id = ds.designation_id
            WHERE e.user_id = %s
        """, (user_id,))

        employee_row = cursor.fetchone()
        if not employee_row and session.get("employee_id"):
            cursor.execute("""
                SELECT
                    e.employee_id,
                    e.employee_code,
                    e.first_name,
                    e.last_name,
                    e.department_id,
                    d.department_name,
                    ds.designation_name,
                    COALESCE(d.casual_leave_limit, 0),
                    COALESCE(d.sick_leave_limit, 0),
                    COALESCE(d.privileged_leave_limit, 0)
                FROM employees e
                LEFT JOIN departments d ON e.department_id = d.department_id
                LEFT JOIN designations ds ON e.designation_id = ds.designation_id
                WHERE e.employee_id = %s
            """, (session.get("employee_id"),))
            employee_row = cursor.fetchone()

        if not employee_row:
            return "Employee profile not found.", 404

        employee = {
            "employee_id": employee_row[0],
            "employee_code": employee_row[1],
            "first_name": employee_row[2] or "",
            "last_name": employee_row[3] or "",
            "department_id": employee_row[4],
            "department": employee_row[5] or "",
            "designation": employee_row[6] or "Employee",
            "name": (
                f"{employee_row[2] or ''} "
                f"{employee_row[3] or ''}"
            ).strip()
        }

        casual_limit = employee_row[7]
        sick_limit = employee_row[8]
        privileged_limit = employee_row[9]

        # ----------------------------------------------------
        # HELPER TO CATEGORIZE LEAVE TYPES
        # ----------------------------------------------------
        def categorize_leave(lt_str):
            lt = (lt_str or "").lower()
            if "casual" in lt:
                return "casual"
            elif "sick" in lt:
                return "sick"
            elif "privilege" in lt or "annual" in lt:
                return "privileged"
            return None

        # ----------------------------------------------------
        # CALCULATE LEAVE BALANCES FOR CURRENT YEAR
        # ----------------------------------------------------
        cursor.execute("""
            SELECT
                leave_type,
                status,
                COALESCE(SUM(number_of_days), 0)
            FROM leave_requests
            WHERE employee_id = %s
              AND EXTRACT(YEAR FROM from_date) = EXTRACT(YEAR FROM CURRENT_DATE)
              AND status IN ('Approved', 'Pending')
            GROUP BY leave_type, status
        """, (employee["employee_id"],))

        leave_usage_rows = cursor.fetchall()

        used_counts = {"casual": 0, "sick": 0, "privileged": 0}
        pending_counts = {"casual": 0, "sick": 0, "privileged": 0}

        for lt, st, days in leave_usage_rows:
            cat = categorize_leave(lt)
            if cat:
                if st == "Approved":
                    used_counts[cat] += int(days)
                elif st == "Pending":
                    pending_counts[cat] += int(days)

        leave_balances = {
            "casual": {
                "limit": casual_limit,
                "used": used_counts["casual"],
                "pending": pending_counts["casual"],
                "available": max(0, casual_limit - used_counts["casual"] - pending_counts["casual"])
            },
            "sick": {
                "limit": sick_limit,
                "used": used_counts["sick"],
                "pending": pending_counts["sick"],
                "available": max(0, sick_limit - used_counts["sick"] - pending_counts["sick"])
            },
            "privileged": {
                "limit": privileged_limit,
                "used": used_counts["privileged"],
                "pending": pending_counts["privileged"],
                "available": max(0, privileged_limit - used_counts["privileged"] - pending_counts["privileged"])
            }
        }

        # ====================================================
        # POST — SUBMIT LEAVE REQUEST
        # ====================================================
        if request.method == "POST":

            leave_type = request.form.get(
                "leave_type",
                ""
            ).strip()

            reason = request.form.get(
                "reason",
                ""
            ).strip()

            start_date_text = request.form.get(
                "start_date",
                ""
            ).strip()

            end_date_text = request.form.get(
                "end_date",
                ""
            ).strip()

            # ------------------------------------------------
            # BASIC VALIDATION
            # ------------------------------------------------
            if not leave_type:
                return render_template(
                    "leave_request.html",
                    employee=employee,
                    leave_balances=leave_balances,
                    submitted=False,
                    error="Please select a leave type."
                )

            if not start_date_text or not end_date_text:
                return render_template(
                    "leave_request.html",
                    employee=employee,
                    leave_balances=leave_balances,
                    submitted=False,
                    error="Please select both start and end dates."
                )

            if not reason:
                return render_template(
                    "leave_request.html",
                    employee=employee,
                    leave_balances=leave_balances,
                    submitted=False,
                    error="Please provide a reason for the leave."
                )

            # ------------------------------------------------
            # PARSE DATES
            # ------------------------------------------------
            try:

                start_date = date.fromisoformat(
                    start_date_text
                )

                end_date = date.fromisoformat(
                    end_date_text
                )

            except ValueError:

                return render_template(
                    "leave_request.html",
                    employee=employee,
                    leave_balances=leave_balances,
                    submitted=False,
                    error="Invalid date format."
                )

            # ------------------------------------------------
            # DATE VALIDATION
            # ------------------------------------------------
            if end_date < start_date:

                return render_template(
                    "leave_request.html",
                    employee=employee,
                    leave_balances=leave_balances,
                    submitted=False,
                    error="End date cannot be before start date."
                )

            # ------------------------------------------------
            # CALCULATE NUMBER OF DAYS
            # ------------------------------------------------
            number_of_days = (
                end_date - start_date
            ).days + 1

            # ------------------------------------------------
            # LEAVE LIMIT / BALANCE VALIDATION
            # ------------------------------------------------
            category = categorize_leave(leave_type)
            if not category:
                return render_template(
                    "leave_request.html",
                    employee=employee,
                    leave_balances=leave_balances,
                    submitted=False,
                    error=f"Unrecognized leave type: {leave_type}"
                )

            available_days = leave_balances[category]["available"]

            if number_of_days > available_days:
                return render_template(
                    "leave_request.html",
                    employee=employee,
                    leave_balances=leave_balances,
                    submitted=False,
                    error=f"Insufficient leave balance. You have {available_days} day(s) available for {leave_type}, but requested {number_of_days} day(s)."
                )

            # ------------------------------------------------
            # PREVENT DUPLICATE SUBMISSION
            # ------------------------------------------------
            cursor.execute("""
                SELECT leave_id FROM leave_requests
                WHERE employee_id = %s
                  AND from_date = %s
                  AND to_date = %s
                  AND LOWER(TRIM(status)) != 'rejected'
            """, (employee["employee_id"], start_date, end_date))
            if cursor.fetchone():
                return render_template(
                    "leave_request.html",
                    employee=employee,
                    leave_balances=leave_balances,
                    submitted=False,
                    error="A leave request for this date range has already been submitted."
                )

            # ------------------------------------------------
            # INSERT LEAVE REQUEST
            # ------------------------------------------------
            cursor.execute("""
                INSERT INTO leave_requests
                (
                    employee_id,
                    leave_type,
                    from_date,
                    to_date,
                    number_of_days,
                    reason,
                    status,
                    applied_on
                )
                VALUES
                (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    'Pending',
                    NOW()
                )
                RETURNING leave_id
            """, (
                employee["employee_id"],
                leave_type,
                start_date,
                end_date,
                number_of_days,
                reason
            ))

            leave_id = cursor.fetchone()[0]

            # Notify reporting manager
            cursor.execute("""
                SELECT m.user_id
                FROM employees e
                JOIN employees m ON e.manager_id = m.employee_id
                WHERE e.employee_id = %s
            """, (employee["employee_id"],))
            mgr_notif_row = cursor.fetchone()
            if mgr_notif_row and mgr_notif_row[0]:
                emp_name = employee.get("name") or f"{employee.get('first_name', '')} {employee.get('last_name', '')}".strip() or "Team member"
                _safe_insert_notification(
                    cursor,
                    mgr_notif_row[0],
                    "Leave Request Submitted",
                    f"{emp_name} has requested {number_of_days} day(s) leave ({leave_type}) from {start_date} to {end_date}.",
                    "leave"
                )

            conn.commit()

            # ------------------------------------------------
            # UPDATE BALANCES FOR IMMEDIATE REFLECTION
            # ------------------------------------------------
            leave_balances[category]["pending"] += number_of_days
            leave_balances[category]["available"] = max(
                0,
                leave_balances[category]["limit"]
                - leave_balances[category]["used"]
                - leave_balances[category]["pending"]
            )

            # ------------------------------------------------
            # SHOW SUCCESS
            # ------------------------------------------------
            return render_template(
                "leave_request.html",
                employee=employee,
                leave_balances=leave_balances,
                submitted=True,
                leave={
                    "leave_id": leave_id,
                    "leave_type": leave_type,
                    "start_date": start_date,
                    "end_date": end_date,
                    "number_of_days": number_of_days,
                    "reason": reason,
                    "status": "Pending"
                }
            )

        # ====================================================
        # GET — DISPLAY FORM
        # ====================================================
        return render_template(
            "leave_request.html",
            employee=employee,
            leave_balances=leave_balances,
            submitted=False
        )

    except Exception as e:

        if conn:
            conn.rollback()

        print(
            "LEAVE REQUEST ERROR:",
            e
        )

        return render_template(
            "leave_request.html",
            employee=employee if "employee" in locals() else None,
            leave_balances=leave_balances if "leave_balances" in locals() else None,
            submitted=False,
            error="The leave request could not be saved."
        )

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()

# ============================================================
# EMPLOYEE REQUESTED LEAVES
# ============================================================

@dashboard_bp.route("/requested_leaves.html")
@dashboard_bp.route("/requested-leaves")
def requested_leaves_page():

    # --------------------------------------------------------
    # LOGIN CHECK
    # --------------------------------------------------------
    if "user_id" not in session:
        return redirect(url_for("login_page"))

    # --------------------------------------------------------
    # AUTHENTICATED USER ACCESS
    # --------------------------------------------------------
    role = session.get("role_name", "").lower()
    norm_role = _normalize_role(role)
    if norm_role not in {"employee", "manager", "hr", "admin"}:
        return "Access Denied", 403

    user_id = session["user_id"]

    conn = None
    cursor = None

    try:

        conn = get_db_connection()
        cursor = conn.cursor()

        # ----------------------------------------------------
        # GET LOGGED-IN EMPLOYEE
        # ----------------------------------------------------
        cursor.execute("""
            SELECT
                e.employee_id,
                e.employee_code,
                e.first_name,
                e.last_name,
                d.department_name,
                ds.designation_name
            FROM employees e
            LEFT JOIN departments d ON e.department_id = d.department_id
            LEFT JOIN designations ds ON e.designation_id = ds.designation_id
            WHERE user_id = %s
        """, (user_id,))

        employee_row = cursor.fetchone()
        if not employee_row and session.get("employee_id"):
            cursor.execute("""
                SELECT
                    e.employee_id,
                    e.employee_code,
                    e.first_name,
                    e.last_name,
                    d.department_name,
                    ds.designation_name
                FROM employees e
                LEFT JOIN departments d ON e.department_id = d.department_id
                LEFT JOIN designations ds ON e.designation_id = ds.designation_id
                WHERE e.employee_id = %s
            """, (session.get("employee_id"),))
            employee_row = cursor.fetchone()

        if not employee_row:
            return "Employee profile not found.", 404

        employee = {
            "employee_id": employee_row[0],
            "employee_code": employee_row[1],
            "first_name": employee_row[2] or "",
            "last_name": employee_row[3] or "",
            "department": employee_row[4] or "",
            "designation": employee_row[5] or "Employee",
            "name": (
                f"{employee_row[2] or ''} "
                f"{employee_row[3] or ''}"
            ).strip()
        }

        # ----------------------------------------------------
        # GET EMPLOYEE'S LEAVE REQUESTS
        # ----------------------------------------------------
        cursor.execute("""
            SELECT
                leave_id,
                leave_type,
                from_date,
                to_date,
                number_of_days,
                reason,
                status,
                applied_on
            FROM leave_requests
            WHERE employee_id = %s
            ORDER BY applied_on DESC, leave_id DESC
        """, (employee["employee_id"],))

        rows = cursor.fetchall()

        leave_requests = []

        for row in rows:

            leave_requests.append({
                "leave_id": row[0],
                "leave_type": row[1],
                "from_date": row[2],
                "to_date": row[3],
                "number_of_days": row[4],
                "reason": row[5],
                "status": row[6],
                "applied_on": row[7]
            })

        # ----------------------------------------------------
        # RENDER PAGE
        # ----------------------------------------------------
        return render_template(
            "requested_leaves.html",
            employee=employee,
            leave_requests=leave_requests
        )

    except Exception as e:

        print(
            "REQUESTED LEAVES ERROR:",
            e
        )

        return (
            "Unable to load leave requests.",
            500
        )

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()

# ============================================================
# MANAGER / HR — APPROVE LEAVE REQUESTS
# ============================================================

@dashboard_bp.route("/approve_leaves.html", methods=["GET", "POST"])
@dashboard_bp.route("/approve-leaves", methods=["GET", "POST"])
def approve_leaves_page():

    # --------------------------------------------------------
    # LOGIN CHECK
    # --------------------------------------------------------

    if "user_id" not in session:
        return redirect(url_for("login_page"))


    # --------------------------------------------------------
    # ROLE CHECK
    # --------------------------------------------------------

    role = session.get(
        "role_name",
        ""
    ).lower()

    norm_role = _normalize_role(role)
    if norm_role not in {"manager", "hr", "admin"}:
        return "Access Denied", 403


    user_id = session["user_id"]

    conn = None
    cursor = None


    try:

        conn = get_db_connection()
        cursor = conn.cursor()


        # ====================================================
        # POST — APPROVE / REJECT
        # ====================================================

        if request.method == "POST":

            data = request.get_json(
                silent=True
            ) or {}


            leave_id = data.get(
                "leave_id"
            )

            status = data.get(
                "status",
                ""
            ).strip()


            # ------------------------------------------------
            # VALIDATION
            # ------------------------------------------------

            try:

                leave_id = int(
                    leave_id
                )

            except (
                TypeError,
                ValueError
            ):

                return jsonify({
                    "success": False,
                    "message":
                        "Invalid leave request."
                }), 400


            if status not in {
                "Approved",
                "Rejected"
            }:

                return jsonify({
                    "success": False,
                    "message":
                        "Invalid leave status."
                }), 400


            # =================================================
            # GET LEAVE REQUEST
            # =================================================

            cursor.execute("""
                SELECT
                    leave_id,
                    employee_id,
                    from_date,
                    to_date,
                    status
                FROM leave_requests
                WHERE leave_id = %s
            """, (
                leave_id,
            ))


            leave_row = cursor.fetchone()


            if not leave_row:

                return jsonify({
                    "success": False,
                    "message":
                        "Leave request not found."
                }), 404


            employee_id = leave_row[1]
            start_date = leave_row[2]
            end_date = leave_row[3]
            current_status = leave_row[4]


            # ------------------------------------------------
            # PREVENT REPROCESSING
            # ------------------------------------------------

            if str(
                current_status
            ).lower() != "pending":

                return jsonify({
                    "success": False,
                    "message":
                        "This leave request has already been processed."
                }), 409


            # =================================================
            # UPDATE LEAVE STATUS & RECORD APPROVER
            # =================================================

            approver_employee_id = session.get("employee_id")
            if not approver_employee_id:
                cursor.execute("SELECT employee_id FROM employees WHERE user_id = %s", (user_id,))
                approver_row = cursor.fetchone()
                approver_employee_id = approver_row[0] if approver_row else None

            cursor.execute("""
                UPDATE leave_requests
                SET status = %s,
                    approved_by = %s
                WHERE leave_id = %s
            """, (
                status,
                approver_employee_id,
                leave_id
            ))


            # =================================================
            # APPROVED LEAVE → ATTENDANCE
            # =================================================

            if status == "Approved":

                current_date = start_date

                while current_date <= end_date:

                    # ----------------------------------------
                    # Check whether attendance already exists
                    # ----------------------------------------

                    cursor.execute("""
                        SELECT attendance_id, status
                        FROM attendance
                        WHERE employee_id = %s
                          AND attendance_date = %s
                    """, (
                        employee_id,
                        current_date
                    ))

                    attendance_row = cursor.fetchone()

                    # ----------------------------------------
                    # Do not overwrite holidays or weekly offs with leave
                    # ----------------------------------------
                    if attendance_row:
                        existing_status = (attendance_row[1] or "").strip().lower()
                        if existing_status not in ("holiday", "weekly off"):
                            cursor.execute("""
                                UPDATE attendance
                                SET status = 'Leave'
                                WHERE attendance_id = %s
                            """, (
                                attendance_row[0],
                            ))
                    else:
                        cursor.execute("""
                            INSERT INTO attendance
                            (
                                employee_id,
                                attendance_date,
                                status
                            )
                            VALUES
                            (
                                %s,
                                %s,
                                'Leave'
                            )
                        """, (
                            employee_id,
                            current_date
                        ))


                    current_date = (
                        current_date
                        + __import__("datetime").timedelta(
                            days=1
                        )
                    )


            # =================================================
            # NOTIFY EMPLOYEE
            # =================================================
            cursor.execute("SELECT user_id FROM employees WHERE employee_id = %s", (employee_id,))
            emp_u_row = cursor.fetchone()
            if emp_u_row and emp_u_row[0]:
                _safe_insert_notification(
                    cursor,
                    emp_u_row[0],
                    f"Leave Request {status}",
                    f"Your leave request from {start_date} to {end_date} has been {status.lower()}.",
                    "leave"
                )

            # =================================================
            # COMMIT
            # =================================================

            conn.commit()


            # =================================================
            # AUDIT LOG
            # =================================================

            try:

                cursor.execute("""
                    INSERT INTO audit_logs
                    (
                        user_id,
                        action,
                        description,
                        ip_address
                    )
                    VALUES
                    (
                        %s,
                        %s,
                        %s,
                        %s
                    )
                """, (
                    user_id,
                    f"Leave {status}",
                    (
                        f"Leave request ID "
                        f"{leave_id} "
                        f"was {status.lower()}."
                    ),
                    request.remote_addr
                ))

                conn.commit()

            except Exception as audit_error:

                print(
                    "LEAVE AUDIT LOG ERROR:",
                    audit_error
                )

                conn.rollback()


            return jsonify({
                "success": True,
                "message":
                    f"Leave request {status.lower()} successfully."
            })


        # ====================================================
        # GET — DISPLAY LEAVE REQUESTS
        # ====================================================

        if norm_role == "manager":
            manager_id = session.get("employee_id")
            if not manager_id:
                cursor.execute("SELECT employee_id FROM employees WHERE user_id = %s", (user_id,))
                mgr_row = cursor.fetchone()
                manager_id = mgr_row[0] if mgr_row else None

            cursor.execute("""
                SELECT
                    lr.leave_id,
                    lr.employee_id,
                    e.employee_code,
                    e.first_name,
                    e.last_name,
                    lr.leave_type,
                    lr.from_date,
                    lr.to_date,
                    lr.number_of_days,
                    lr.reason,
                    lr.status,
                    lr.applied_on
                FROM leave_requests lr
                INNER JOIN employees e
                    ON lr.employee_id = e.employee_id
                WHERE e.manager_id = %s
                ORDER BY
                    CASE
                        WHEN LOWER(TRIM(lr.status)) = 'pending'
                        THEN 0
                        ELSE 1
                    END,
                    lr.applied_on DESC,
                    lr.leave_id DESC
            """, (manager_id,))
        else:
            cursor.execute("""
                SELECT
                    lr.leave_id,
                    lr.employee_id,
                    e.employee_code,
                    e.first_name,
                    e.last_name,
                    lr.leave_type,
                    lr.from_date,
                    lr.to_date,
                    lr.number_of_days,
                    lr.reason,
                    lr.status,
                    lr.applied_on
                FROM leave_requests lr
                INNER JOIN employees e
                    ON lr.employee_id = e.employee_id
                ORDER BY
                    CASE
                        WHEN LOWER(TRIM(lr.status)) = 'pending'
                        THEN 0
                        ELSE 1
                    END,
                    lr.applied_on DESC,
                    lr.leave_id DESC
            """)


        rows = cursor.fetchall()


        leave_requests = []


        for row in rows:

            leave_requests.append({

                "leave_id":
                    row[0],

                "employee_id":
                    row[1],

                "employee_code":
                    row[2],

                "employee_name":
                    (
                        f"{row[3] or ''} "
                        f"{row[4] or ''}"
                    ).strip(),

                "leave_type":
                    row[5],

                "from_date":
                    row[6],

                "to_date":
                    row[7],

                "number_of_days":
                    row[8],

                "reason":
                    row[9],

                "status":
                    row[10],

                "applied_on":
                    row[11]
            })


        # ====================================================
        # RENDER PAGE
        # ====================================================

        return render_template(
            "approve_leaves.html",
            leave_requests=leave_requests,
            user_name=session.get(
                "username",
                "User"
            ),
            user_role=role.upper()
        )


    except Exception as e:

        if conn:
            conn.rollback()


        print(
            "APPROVE LEAVES ERROR:",
            e
        )


        if request.method == "POST":

            return jsonify({
                "success": False,
                "message":
                    "Unable to process leave request."
            }), 500


        return (
            "Unable to load leave requests.",
            500
        )


    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()
# ============================================================
# BEHAVIOUR RATING PAGE
# ============================================================

@dashboard_bp.route("/behaviour_rating.html")
@dashboard_bp.route("/behaviour-rating")
def behaviour_rating_page():

    # --------------------------------------------------------
    # LOGIN CHECK
    # --------------------------------------------------------
    if "user_id" not in session:
        return redirect(url_for("login_page"))

    # --------------------------------------------------------
    # MANAGER ACCESS ONLY
    # --------------------------------------------------------
    if session.get("role_name", "").lower() != "manager":
        return "Access Denied", 403

    conn = None
    cursor = None

    try:

        conn = get_db_connection()
        cursor = conn.cursor()

        # ====================================================
        # GET LOGGED-IN MANAGER
        # ====================================================

        cursor.execute("""
            SELECT
                employee_id,
                employee_code,
                first_name,
                last_name
            FROM employees
            WHERE user_id = %s
        """, (
            session["user_id"],
        ))

        manager_row = cursor.fetchone()
        if not manager_row and session.get("employee_id"):
            cursor.execute("""
                SELECT
                    employee_id,
                    employee_code,
                    first_name,
                    last_name
                FROM employees
                WHERE employee_id = %s
            """, (session.get("employee_id"),))
            manager_row = cursor.fetchone()

        if not manager_row:
            return "Manager profile not found.", 404

        manager_id = manager_row[0]
        manager_code = manager_row[1]
        manager_name = (
            f"{manager_row[2] or ''} "
            f"{manager_row[3] or ''}"
        ).strip()


        # ====================================================
        # GET MANAGER'S EMPLOYEES
        # ====================================================

        cursor.execute("""
            SELECT
                e.employee_id,
                e.employee_code,
                e.first_name,
                e.last_name,
                des.designation_name
            FROM employees e

            LEFT JOIN designations des
                ON e.designation_id = des.designation_id

            WHERE e.manager_id = %s

            ORDER BY
                e.first_name,
                e.last_name
        """, (
            manager_id,
        ))

        employee_rows = cursor.fetchall()

        employees = []

        for row in employee_rows:

            employees.append({
                "employee_id": row[0],
                "employee_code": row[1],
                "name": (
                    f"{row[2] or ''} "
                    f"{row[3] or ''}"
                ).strip(),
                "designation": (
                    row[4]
                    if row[4]
                    else "Designation Not Assigned"
                )
            })


        # ====================================================
        # GET LATEST APPRAISAL CYCLE FOR MANAGER'S TEAM
        # ====================================================

        cursor.execute("""
            SELECT
                ac.cycle_id,
                ac.cycle_name
            FROM self_appraisal sa
            INNER JOIN appraisal_cycles ac
                ON sa.cycle_id = ac.cycle_id
            INNER JOIN employees e
                ON sa.employee_id = e.employee_id
            WHERE e.manager_id = %s
            ORDER BY
                sa.created_at DESC,
                sa.self_appraisal_id DESC
            LIMIT 1
        """, (
            manager_id,
        ))

        cycle_row = cursor.fetchone()

        if not cycle_row:
            cursor.execute("""
                SELECT cycle_id, cycle_name
                FROM appraisal_cycles
                WHERE status = 'Active'
                ORDER BY cycle_id DESC
                LIMIT 1
            """)
            cycle_row = cursor.fetchone()

        cycle_id = cycle_row[0] if cycle_row else None
        appraisal_cycle = (
            cycle_row[1]
            if cycle_row
            else "No Active Cycle"
        )


        # ====================================================
        # RETURN PAGE
        # ====================================================

        return render_template(
            "behaviour_rating.html",
            employees=employees,
            manager={
                "employee_id": manager_id,
                "employee_code": manager_code,
                "name": manager_name
            },
            appraisal_cycle=appraisal_cycle,
            cycle_id=cycle_id
        )


    except Exception as e:

        print(
            "BEHAVIOUR RATING PAGE ERROR:",
            e
        )

        return (
            "Unable to load Behaviour Rating page.",
            500
        )


    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()

# ============================================================
# EXPLICIT UI PAGE ROUTES & ENDPOINTS
# ============================================================

@dashboard_bp.route("/hr_dashboard.html")
@dashboard_bp.route("/hr-dashboard")
def hr_dashboard_page():
    return _render_additional_page("hr_dashboard.html", {"hr", "admin"})

@dashboard_bp.route("/admin_dashboard.html")
@dashboard_bp.route("/admin-dashboard")
def admin_dashboard_page():
    return _render_additional_page("hr_dashboard.html", {"admin"})

@dashboard_bp.route("/profile.html")
@dashboard_bp.route("/profile")
def profile():
    return _render_additional_page("profile.html", {"employee", "manager", "hr", "admin"})

@dashboard_bp.route("/my_appraisals.html")
@dashboard_bp.route("/my-appraisals")
def my_appraisals_page():
    return _render_additional_page("my_appraisals.html", {"employee", "manager"})

@dashboard_bp.route("/employee_training.html")
@dashboard_bp.route("/employee-training")
def employee_training_page():
    if "user_id" not in session:
        return redirect(url_for("login_page"))
    role = session.get("role_name", "")
    if _normalize_role(role) not in ["employee", "manager"]:
        return "Access Denied", 403

    user_id = session["user_id"]
    conn = get_db_connection()
    cur = conn.cursor()
    trainings = []
    emp_id = None
    try:
        cur.execute("""
            SELECT e.employee_id
            FROM employees e
            WHERE e.user_id = %s
        """, (user_id,))
        emp_row = cur.fetchone()
        if not emp_row and session.get("employee_id"):
            emp_id = session.get("employee_id")
        elif emp_row:
            emp_id = emp_row[0]

        if emp_id:
            try:
                from routes.training_routes import compute_employee_training_status, sync_training_statuses
                sync_training_statuses(cur)
                conn.commit()
            except Exception:
                pass

            from routes.training_routes import compute_employee_training_status, compute_session_status

            def _fmt_time(val):
                if val is None:
                    return None
                if hasattr(val, "strftime"):
                    return val.strftime("%H:%M")
                return str(val)[:5]

            def _fmt_date(val):
                if val is None:
                    return None
                if hasattr(val, "strftime"):
                    return val.strftime("%d %b %Y")
                return str(val)

            cur.execute("""
                SELECT 
                    ts.program_id, 
                    ts.session_id, 
                    ts.session_name,
                    ts.session_date, 
                    ts.start_time, 
                    ts.end_time,
                    COALESCE(ta.attendance_status, 'Not Marked') AS attendance_status
                FROM training_sessions ts
                JOIN training_records tr ON ts.program_id = tr.program_id
                LEFT JOIN training_attendance ta 
                    ON ta.session_id = ts.session_id 
                   AND ta.employee_id = tr.employee_id
                WHERE tr.employee_id = %s
                ORDER BY ts.session_date, ts.start_time, ts.session_id
            """, (emp_id,))
            s_rows = cur.fetchall()
            prog_sessions = {}
            for s in s_rows:
                p_id = s[0]
                s_id = s[1]
                s_name = s[2] or f"Session {s_id}"
                s_date = s[3]
                st_time = s[4]
                end_time = s[5]
                att_status = s[6]
                s_status = compute_session_status(s_date, st_time, end_time)

                prog_sessions.setdefault(p_id, []).append({
                    "session_id": s_id,
                    "session_name": s_name,
                    "session_date": _fmt_date(s_date),
                    "session_date_raw": s_date.isoformat() if hasattr(s_date, "isoformat") else (str(s_date) if s_date else None),
                    "start_time": _fmt_time(st_time),
                    "end_time": _fmt_time(end_time),
                    "attendance_status": att_status,
                    "status": s_status
                })

            cur.execute("""
                SELECT 
                    tr.training_id,
                    tr.training_name,
                    tr.training_type,
                    tr.trainer_name,
                    tr.start_date,
                    tr.end_date,
                    tr.status,
                    tr.score,
                    tr.certificate,
                    tr.certificate_file,
                    tr.program_id,
                    COALESCE(tp.remarks, tr.remarks, '') AS remarks
                FROM training_records tr
                LEFT JOIN training_programs tp ON tp.program_id = tr.program_id
                WHERE tr.employee_id = %s
                ORDER BY tr.start_date DESC NULLS LAST, tr.training_id DESC
            """, (emp_id,))
            rows = cur.fetchall()
            trainings = []
            for r in rows:
                p_id = r[10]
                p_sessions = prog_sessions.get(p_id, [])
                total_sess = len(p_sessions)
                attended_sess = sum(1 for s in p_sessions if s.get("attendance_status") == "Attended")
                absent_sess = sum(1 for s in p_sessions if s.get("attendance_status") == "Absent")
                leave_sess = sum(1 for s in p_sessions if s.get("attendance_status") == "Approved Leave")

                computed_status = compute_employee_training_status(
                    r[4], r[5],
                    [{"session_date": s["session_date_raw"], "start_time": s["start_time"], "end_time": s["end_time"]} for s in p_sessions],
                    certificate=bool(r[8])
                )

                trainings.append({
                    "training_id": r[0],
                    "training_name": r[1],
                    "training_type": r[2],
                    "trainer_name": r[3],
                    "start_date": _fmt_date(r[4]),
                    "end_date": _fmt_date(r[5]),
                    "status": computed_status,
                    "score": float(r[7]) if r[7] is not None else None,
                    "certificate": bool(r[8]),
                    "certificate_file": r[9],
                    "program_id": p_id,
                    "program_code": f"TR{str(p_id).zfill(3)}" if p_id else f"TR{str(r[0]).zfill(3)}",
                    "remarks": r[11] or "No specific remarks or description provided.",
                    "sessions": p_sessions,
                    "total_sessions": total_sess,
                    "attended_sessions": attended_sess,
                    "absent_sessions": absent_sess,
                    "leave_sessions": leave_sess
                })
    except Exception as e:
        print("Employee Training Query Error:", e)
    finally:
        cur.close()
        conn.close()

    return render_template("employee_training.html", trainings=trainings, employee_id=emp_id)

@dashboard_bp.route("/review_attendance.html")
@dashboard_bp.route("/review-attendance")
def review_attendance_page():
    if "user_id" not in session:
        return redirect(url_for("login_page"))

    role = _normalize_role(session.get("role_name", ""))
    if role not in {"manager", "hr", "admin"}:
        return "Access Denied", 403

    user_id = session["user_id"]
    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Find manager's employee_id if manager
        manager_id = None
        if role == "manager":
            cur.execute("SELECT employee_id FROM employees WHERE user_id = %s", (user_id,))
            mgr_row = cur.fetchone()
            if not mgr_row and session.get("employee_id"):
                cur.execute("SELECT employee_id FROM employees WHERE employee_id = %s", (session.get("employee_id"),))
                mgr_row = cur.fetchone()
            if mgr_row:
                manager_id = mgr_row[0]

        # Query team employees or all employees for HR
        if role == "manager" and manager_id:
            cur.execute("""
                SELECT
                    e.employee_id,
                    e.employee_code,
                    e.first_name,
                    e.last_name,
                    COALESCE(d.department_name, '—'),
                    COALESCE(des.designation_name, '—'),
                    COUNT(*) FILTER (WHERE LOWER(TRIM(a.status)) NOT IN ('weekly off', 'holiday')) AS working_days,
                    COUNT(*) FILTER (WHERE LOWER(TRIM(a.status)) = 'present') AS present_days,
                    COUNT(*) FILTER (WHERE LOWER(TRIM(a.status)) = 'leave') AS leave_days,
                    COUNT(*) FILTER (WHERE LOWER(TRIM(a.status)) IN ('half day', 'half-day')) AS half_days
                FROM employees e
                LEFT JOIN departments d ON e.department_id = d.department_id
                LEFT JOIN designations des ON e.designation_id = des.designation_id
                LEFT JOIN attendance a ON a.employee_id = e.employee_id
                WHERE e.manager_id = %s
                GROUP BY e.employee_id, e.employee_code, e.first_name, e.last_name, d.department_name, des.designation_name
                ORDER BY e.first_name, e.last_name
            """, (manager_id,))
        else:
            cur.execute("""
                SELECT
                    e.employee_id,
                    e.employee_code,
                    e.first_name,
                    e.last_name,
                    COALESCE(d.department_name, '—'),
                    COALESCE(des.designation_name, '—'),
                    COUNT(*) FILTER (WHERE LOWER(TRIM(a.status)) NOT IN ('weekly off', 'holiday')) AS working_days,
                    COUNT(*) FILTER (WHERE LOWER(TRIM(a.status)) = 'present') AS present_days,
                    COUNT(*) FILTER (WHERE LOWER(TRIM(a.status)) = 'leave') AS leave_days,
                    COUNT(*) FILTER (WHERE LOWER(TRIM(a.status)) IN ('half day', 'half-day')) AS half_days
                FROM employees e
                LEFT JOIN departments d ON e.department_id = d.department_id
                LEFT JOIN designations des ON e.designation_id = des.designation_id
                LEFT JOIN attendance a ON a.employee_id = e.employee_id
                GROUP BY e.employee_id, e.employee_code, e.first_name, e.last_name, d.department_name, des.designation_name
                ORDER BY e.first_name, e.last_name
            """)

        rows = cur.fetchall()
        attendance_list = []

        for row in rows:
            emp_id = row[0]
            emp_code = row[1] or ""
            emp_name = f"{row[2] or ''} {row[3] or ''}".strip()
            dept = row[4]
            desig = row[5]
            working_days = row[6] or 0
            present_days = row[7] or 0
            leave_days = row[8] or 0
            half_days = row[9] or 0

            att_pct = calculate_attendance_percentage(present_days, working_days, half_days)
            score_10 = round(att_pct / 10.0, 1)

            if working_days == 0:
                status_label = "No Records"
                badge_class = "bg-secondary text-white"
                pct_badge_class = "bg-light text-muted"
            elif att_pct >= 90:
                status_label = "Excellent"
                badge_class = "bg-success text-white"
                pct_badge_class = "bg-success text-white"
            elif att_pct >= 80:
                status_label = "Regular"
                badge_class = "bg-primary text-white"
                pct_badge_class = "bg-primary text-white"
            elif att_pct >= 75:
                status_label = "Average"
                badge_class = "bg-warning text-dark"
                pct_badge_class = "bg-warning text-dark"
            else:
                status_label = "Low Attendance"
                badge_class = "bg-danger text-white"
                pct_badge_class = "bg-danger text-white"

            attendance_list.append({
                "employee_id": emp_id,
                "employee_code": emp_code,
                "employee_name": emp_name,
                "department": dept,
                "designation": desig,
                "working_days": working_days,
                "present_days": present_days,
                "leave_days": leave_days,
                "half_days": half_days,
                "attendance_percentage": round(att_pct, 1),
                "score_10": score_10,
                "status_label": status_label,
                "badge_class": badge_class,
                "pct_badge_class": pct_badge_class
            })

        return render_template(
            "review_attendance.html",
            attendance_list=attendance_list
        )

    except Exception as e:
        print("REVIEW ATTENDANCE ERROR:", e)
        return "Unable to load attendance review.", 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

@dashboard_bp.route("/feedback_360.html", methods=["GET", "POST"])
@dashboard_bp.route("/feedback-360", methods=["GET", "POST"])
def feedback_360_page():
    if "user_id" not in session:
        return redirect(url_for("login_page"))

    role = session.get("role_name", "").lower()
    norm_role = _normalize_role(role)
    if norm_role not in {"manager", "hr", "admin"}:
        return "Access Denied", 403

    user_id = session["user_id"]
    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Find logged in reviewer employee record
        cursor.execute("""
            SELECT employee_id, employee_code, first_name, last_name
            FROM employees
            WHERE user_id = %s
        """, (user_id,))
        reviewer_row = cursor.fetchone()

        manager_id = reviewer_row[0] if reviewer_row else user_id
        manager_code = reviewer_row[1] if reviewer_row else ""
        manager_name = (
            f"{reviewer_row[2] or ''} {reviewer_row[3] or ''}".strip()
            if reviewer_row
            else session.get("username", "Manager")
        )

        # Get active appraisal cycle
        cursor.execute("""
            SELECT cycle_id, cycle_name
            FROM appraisal_cycles
            WHERE status = 'Active'
            ORDER BY cycle_id DESC
            LIMIT 1
        """)
        cycle_row = cursor.fetchone()
        cycle_id = cycle_row[0] if cycle_row else 1
        appraisal_cycle = cycle_row[1] if cycle_row else "Annual Appraisal 2026-27"

        if request.method == "POST":
            target_employee_id = int(request.form.get("employee_id"))
            reviewer_type = request.form.get("reviewer_type", "Manager")
            rating = float(request.form.get("rating", 3))
            strengths = request.form.get("strengths", "").strip()
            improvement_areas = request.form.get("improvement_areas", "").strip()
            comments = request.form.get("comments", "").strip()

            cursor.execute("""
                INSERT INTO feedback_360
                (
                    employee_id,
                    reviewer_id,
                    cycle_id,
                    reviewer_type,
                    rating,
                    strengths,
                    improvement_areas,
                    comments,
                    submitted_on,
                    created_at
                )
                VALUES
                (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s,
                    CURRENT_DATE,
                    CURRENT_TIMESTAMP
                )
            """, (
                target_employee_id,
                manager_id,
                cycle_id,
                reviewer_type,
                int(round(rating)),
                strengths,
                improvement_areas,
                comments
            ))
            conn.commit()

            return redirect(url_for("dashboard.feedback_360_page", success=1))

        # GET request - load active employees
        cursor.execute("""
            SELECT
                e.employee_id,
                e.employee_code,
                e.first_name,
                e.last_name,
                des.designation_name,
                d.department_name
            FROM employees e
            LEFT JOIN designations des ON e.designation_id = des.designation_id
            LEFT JOIN departments d ON e.department_id = d.department_id
            WHERE e.employment_status = 'Active'
              AND e.employee_id != %s
            ORDER BY e.first_name, e.last_name
        """, (manager_id,))

        emp_rows = cursor.fetchall()
        employees = [
            {
                "employee_id": r[0],
                "employee_code": r[1] or "",
                "name": f"{r[2] or ''} {r[3] or ''}".strip(),
                "designation": r[4] or "Designation Not Assigned",
                "department": r[5] or "General"
            }
            for r in emp_rows
        ]

        success_msg = "360° Multi-Rater Feedback submitted successfully!" if request.args.get("success") == "1" else None

        return render_template(
            "feedback_360.html",
            employees=employees,
            manager={
                "employee_id": manager_id,
                "employee_code": manager_code,
                "name": manager_name
            },
            appraisal_cycle=appraisal_cycle,
            success_msg=success_msg
        )

    except Exception as e:
        if conn:
            conn.rollback()
        print("FEEDBACK 360 ERROR:", e)
        return f"Unable to process 360 Feedback: {e}", 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@dashboard_bp.route("/manage_training.html")
@dashboard_bp.route("/manage-training")
def manage_training_page():
    return _render_additional_page("manage_training.html", {"hr", "admin"})

@dashboard_bp.route("/training_details.html")
@dashboard_bp.route("/training-details")
@dashboard_bp.route("/training-details/<int:program_id>")
def training_details_page(program_id=None):
    if "user_id" not in session:
        return redirect(url_for("login_page"))
    role = _normalize_role(session.get("role_name", ""))
    if role in ["employee", "manager"]:
        if program_id:
            return redirect(f"/employee-training?program_id={program_id}")
        return redirect("/employee-training")
    return _render_additional_page("training_details.html", {"hr", "admin"})

@dashboard_bp.route("/performance_results.html")
@dashboard_bp.route("/performance-results")
def performance_results_page():
    return _render_additional_page("performance_results.html", {"hr", "admin"})

@dashboard_bp.route("/employee_performance_details.html")
@dashboard_bp.route("/employee-performance-details")
@dashboard_bp.route("/employee-performance-details/<int:employee_id>")
def employee_performance_details_page(employee_id=None):
    return _render_additional_page("employee_performance_details.html", {"hr", "admin"})

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
# EMPLOYEE SELF-APPRAISAL FORM
# ============================================================

@dashboard_bp.route("/appraisal_form.html", methods=["GET", "POST"])
@dashboard_bp.route("/appraisal-form", methods=["GET", "POST"])
def appraisal_form_page():

    # --------------------------------------------------------
    # LOGIN CHECK
    # --------------------------------------------------------
    if "user_id" not in session:
        return redirect(url_for("login_page"))

    # --------------------------------------------------------
    # EMPLOYEE & MANAGER SELF-SERVICE ACCESS
    # --------------------------------------------------------
    role = session.get("role_name", "")

    if _normalize_role(role) not in ["employee", "manager"]:
        return "Access Denied", 403

    user_id = session["user_id"]

    conn = None
    cursor = None

    try:

        conn = get_db_connection()
        cursor = conn.cursor()

        # ====================================================
        # GET LOGGED-IN EMPLOYEE
        # ====================================================

        cursor.execute("""
            SELECT
                e.employee_id,
                e.employee_code,
                e.first_name,
                e.last_name,
                e.department_id,
                e.designation_id
            FROM employees e
            WHERE e.user_id = %s
        """, (user_id,))

        employee_row = cursor.fetchone()
        if not employee_row and session.get("employee_id"):
            cursor.execute("""
                SELECT
                    e.employee_id,
                    e.employee_code,
                    e.first_name,
                    e.last_name,
                    e.department_id,
                    e.designation_id
                FROM employees e
                WHERE e.employee_id = %s
            """, (session.get("employee_id"),))
            employee_row = cursor.fetchone()

        if not employee_row:
            return "Employee profile not found.", 404

        (
            employee_id,
            employee_code,
            first_name,
            last_name,
            department_id,
            designation_id
        ) = employee_row

        # ====================================================
        # GET DEPARTMENT
        # ====================================================

        cursor.execute("""
            SELECT department_name
            FROM departments
            WHERE department_id = %s
        """, (department_id,))

        department_row = cursor.fetchone()

        department = (
            department_row[0]
            if department_row
            else "Department Not Assigned"
        )

        # ====================================================
        # GET DESIGNATION
        # ====================================================

        cursor.execute("""
            SELECT designation_name
            FROM designations
            WHERE designation_id = %s
        """, (designation_id,))

        designation_row = cursor.fetchone()

        designation = (
            designation_row[0]
            if designation_row
            else "Designation Not Assigned"
        )

        # ====================================================
        # EMPLOYEE OBJECT
        # ====================================================

        employee = {
            "employee_id": employee_id,
            "employee_code": employee_code,
            "first_name": first_name or "",
            "last_name": last_name or "",
            "name": (
                f"{first_name or ''} "
                f"{last_name or ''}"
            ).strip(),
            "department": department,
            "designation": designation
        }

        # ====================================================
        # GET EXISTING SELF-APPRAISAL
        # ====================================================

        cursor.execute("""
            SELECT
                sa.self_appraisal_id,
                sa.cycle_id,
                ac.cycle_name,
                sa.achievements,
                sa.challenges,
                sa.certifications,
                sa.training_completed,
                sa.future_goals,
                sa.suggestions,
                sa.submission_status,
                sa.submitted_on,
                sa.created_at,
                sa.updated_at,
                sa.self_score
            FROM self_appraisal sa
            LEFT JOIN appraisal_cycles ac
                ON sa.cycle_id = ac.cycle_id
            WHERE sa.employee_id = %s
            ORDER BY sa.created_at DESC,
                     sa.self_appraisal_id DESC
            LIMIT 1
        """, (employee_id,))

        appraisal_row = cursor.fetchone()

        self_appraisal = None

        if appraisal_row:

            score_val = float(appraisal_row[13]) if appraisal_row[13] is not None else None
            rating_val = int(round(score_val / 20.0)) if score_val is not None else None

            self_appraisal = {
                "self_appraisal_id": appraisal_row[0],
                "cycle_id": appraisal_row[1],
                "appraisal_cycle": appraisal_row[2] or f"Cycle {appraisal_row[1]}",
                "cycle_name": appraisal_row[2] or f"Cycle {appraisal_row[1]}",
                "achievements": appraisal_row[3],
                "challenges": appraisal_row[4],
                "certifications": appraisal_row[5],
                "training_completed": appraisal_row[6],
                "future_goals": appraisal_row[7],
                "suggestions": appraisal_row[8],
                "submission_status": appraisal_row[9],
                "submitted_on": appraisal_row[10],
                "created_at": appraisal_row[11],
                "updated_at": appraisal_row[12],
                "self_score": score_val,
                "self_rating": rating_val
            }

        # ====================================================
        # GET APPRAISAL CYCLES
        #
        # For a new submission:
        #     show active cycles.
        #
        # For editing:
        #     also include the existing cycle even if it is
        #     no longer active.
        # ====================================================

        if self_appraisal and self_appraisal.get("cycle_id"):

            cursor.execute("""
                SELECT
                    cycle_id,
                    cycle_name,
                    start_date,
                    end_date,
                    status
                FROM appraisal_cycles
                WHERE LOWER(TRIM(status)) = 'active'
                   OR cycle_id = %s
                ORDER BY start_date DESC,
                         cycle_id DESC
            """, (
                self_appraisal["cycle_id"],
            ))

        else:

            cursor.execute("""
                SELECT
                    cycle_id,
                    cycle_name,
                    start_date,
                    end_date,
                    status
                FROM appraisal_cycles
                WHERE LOWER(TRIM(status)) = 'active'
                ORDER BY start_date DESC,
                         cycle_id DESC
            """)

        cycle_rows = cursor.fetchall()

        appraisal_cycles = []

        for row in cycle_rows:

            appraisal_cycles.append({
                "cycle_id": row[0],
                "cycle_name": row[1],
                "start_date": row[2],
                "end_date": row[3],
                "status": row[4]
            })

        # ====================================================
        # GET EMPLOYEE CERTIFICATIONS
        # ====================================================

        cursor.execute("""
            SELECT
                certification_id,
                certification_name,
                file_name,
                file_path,
                file_type,
                issued_date,
                expiry_date,
                uploaded_at
            FROM certifications
            WHERE employee_id = %s
            ORDER BY uploaded_at DESC, certification_id DESC
        """, (employee_id,))

        cert_rows = cursor.fetchall()

        certificates = []
        for crow in cert_rows:
            certificates.append({
                "certification_id": crow[0],
                "certification_name": crow[1],
                "file_name": crow[2],
                "file_path": crow[3],
                "file_type": crow[4] or "FILE",
                "issued_date": crow[5],
                "expiry_date": crow[6],
                "uploaded_at": crow[7]
            })

        latest_certificate = certificates[0] if certificates else None

        # ====================================================
        # HANDLE FORM SUBMISSION
        # ====================================================

        if request.method == "POST":

            cycle_id_raw = (
                request.form.get("cycle_id", "").strip()
                or request.form.get("appraisal_cycle", "").strip()
            )
            cycle_id = None
            if cycle_id_raw.isdigit():
                cycle_id = int(cycle_id_raw)
            elif cycle_id_raw:
                cursor.execute(
                    "SELECT cycle_id FROM appraisal_cycles WHERE cycle_name = %s LIMIT 1",
                    (cycle_id_raw,)
                )
                match_row = cursor.fetchone()
                if match_row:
                    cycle_id = match_row[0]

            achievements = request.form.get(
                "achievements",
                ""
            ).strip()

            challenges = request.form.get(
                "challenges",
                ""
            ).strip()

            certifications = request.form.get(
                "certifications",
                ""
            ).strip()

            training_completed = request.form.get(
                "training_completed",
                ""
            ).strip()

            future_goals = request.form.get(
                "future_goals",
                ""
            ).strip()

            suggestions = request.form.get(
                "suggestions",
                ""
            ).strip()

            # Read employee overall self-rating (1-5 scale)
            overall_self_rating_raw = request.form.get(
                "overall_self_rating", ""
            ).strip()

            # Certificate file upload (optional)
            certificate_file = request.files.get("certificate_file")
            certificate_name_input = request.form.get("certificate_name", "").strip()
            certificate_issue_date_raw = request.form.get("certificate_issue_date", "").strip()
            certificate_expiry_date_raw = request.form.get("certificate_expiry_date", "").strip()

            if certificate_file and certificate_file.filename:
                orig_filename = certificate_file.filename
                ext = os.path.splitext(orig_filename)[1].lower()
                allowed_extensions = {".pdf", ".jpg", ".jpeg", ".png"}
                if ext not in allowed_extensions:
                    return render_template(
                        "appraisal_form.html",
                        employee=employee,
                        self_appraisal=self_appraisal,
                        appraisal_cycles=appraisal_cycles,
                        latest_certificate=latest_certificate,
                        certificates=certificates,
                        error="Invalid certificate file type. Allowed formats: PDF, JPG, JPEG, PNG."
                    )

            # =================================================
            # VALIDATION
            # =================================================

            if not cycle_id:

                return render_template(
                    "appraisal_form.html",
                    employee=employee,
                    self_appraisal=self_appraisal,
                    appraisal_cycles=appraisal_cycles,
                    latest_certificate=latest_certificate,
                    certificates=certificates,
                    error="Please select an appraisal cycle."
                )

            if not achievements:

                return render_template(
                    "appraisal_form.html",
                    employee=employee,
                    self_appraisal=self_appraisal,
                    appraisal_cycles=appraisal_cycles,
                    latest_certificate=latest_certificate,
                    certificates=certificates,
                    error="Please enter your achievements."
                )

            # Validate overall self-rating and compute self_score (1-5 scale -> 0-100 score)
            self_rating = None
            self_score = None
            if overall_self_rating_raw:
                try:
                    self_rating = int(overall_self_rating_raw)
                    if self_rating < 1 or self_rating > 5:
                        return render_template(
                            "appraisal_form.html",
                            employee=employee,
                            self_appraisal=self_appraisal,
                            appraisal_cycles=appraisal_cycles,
                            latest_certificate=latest_certificate,
                            certificates=certificates,
                            error="Please select an overall self-rating between 1 and 5."
                        )
                    self_score = round(self_rating * 20.0, 2)
                except ValueError:
                    return render_template(
                        "appraisal_form.html",
                        employee=employee,
                        self_appraisal=self_appraisal,
                        appraisal_cycles=appraisal_cycles,
                        latest_certificate=latest_certificate,
                        certificates=certificates,
                        error="Invalid overall self-rating."
                    )
            elif self_appraisal and self_appraisal.get("self_score") is not None:
                self_score = float(self_appraisal["self_score"])
            else:
                self_rating = 4
                self_score = 80.0

            # =================================================
            # PROCESS CERTIFICATE FILE UPLOAD (OPTIONAL)
            # =================================================

            if certificate_file and certificate_file.filename:
                orig_filename = certificate_file.filename
                ext = os.path.splitext(orig_filename)[1].lower()
                safe_name = secure_filename(orig_filename)
                if not safe_name:
                    safe_name = f"certificate{ext}"

                cert_folder = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "static",
                    "certificates"
                )
                os.makedirs(cert_folder, exist_ok=True)

                unique_filename = f"cert_emp_{employee_id}_{int(datetime.now().timestamp())}_{safe_name}"
                dest_path = os.path.join(cert_folder, unique_filename)
                certificate_file.save(dest_path)

                rel_path = f"certificates/{unique_filename}"
                cert_display_name = (
                    certificate_name_input
                    or os.path.splitext(orig_filename)[0].replace("_", " ").title()
                )
                file_type = ext.replace(".", "").upper()

                issue_date = None
                if certificate_issue_date_raw:
                    try:
                        issue_date = datetime.strptime(certificate_issue_date_raw, "%Y-%m-%d").date()
                    except ValueError:
                        pass

                expiry_date = None
                if certificate_expiry_date_raw:
                    try:
                        expiry_date = datetime.strptime(certificate_expiry_date_raw, "%Y-%m-%d").date()
                    except ValueError:
                        pass

                cursor.execute("""
                    INSERT INTO certifications (
                        employee_id,
                        certification_name,
                        file_name,
                        file_path,
                        file_type,
                        issued_date,
                        expiry_date,
                        uploaded_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                """, (
                    employee_id,
                    cert_display_name,
                    unique_filename,
                    rel_path,
                    file_type,
                    issue_date,
                    expiry_date
                ))

                if not certifications:
                    certifications = cert_display_name

            # =================================================
            # UPDATE EXISTING APPRAISAL
            # =================================================

            if self_appraisal:

                cursor.execute("""
                    UPDATE self_appraisal
                    SET
                        cycle_id = %s,
                        achievements = %s,
                        challenges = %s,
                        certifications = %s,
                        training_completed = %s,
                        future_goals = %s,
                        suggestions = %s,
                        self_score = %s,
                        submission_status = 'Submitted',
                        submitted_on = NOW(),
                        updated_at = NOW()
                    WHERE self_appraisal_id = %s
                """, (
                    cycle_id,
                    achievements,
                    challenges,
                    certifications,
                    training_completed,
                    future_goals,
                    suggestions,
                    self_score,
                    self_appraisal["self_appraisal_id"]
                ))

            # =================================================
            # CREATE NEW APPRAISAL
            # =================================================

            else:

                cursor.execute("""
                    INSERT INTO self_appraisal
                    (
                        employee_id,
                        cycle_id,
                        achievements,
                        challenges,
                        certifications,
                        training_completed,
                        future_goals,
                        suggestions,
                        self_score,
                        submission_status,
                        submitted_on
                    )
                    VALUES
                    (
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        'Submitted',
                        NOW()
                    )
                """, (
                    employee_id,
                    cycle_id,
                    achievements,
                    challenges,
                    certifications,
                    training_completed,
                    future_goals,
                    suggestions,
                    self_score
                ))

            # =================================================
            # CREATE MANAGER NOTIFICATION
            # =================================================

            cursor.execute("""
                SELECT
                    m.user_id
                FROM employees e
                JOIN employees m
                    ON e.manager_id = m.employee_id
                WHERE e.employee_id = %s
            """, (employee_id,))

            manager_row = cursor.fetchone()

            if manager_row and manager_row[0]:
                manager_user_id = manager_row[0]

                _safe_insert_notification(
                    cursor,
                    manager_user_id,
                    "Self-Appraisal Submitted",
                    "An employee has submitted a self-appraisal for your review.",
                    "appraisal"
                )

            # =================================================
            # COMMIT
            # =================================================

            conn.commit()

            # =================================================
            # RETURN TO SELF-APPRAISAL SUMMARY
            # =================================================

            return redirect(
                url_for(
                    "dashboard.self_appraisal_page"
                )
            )

        # ====================================================
        # DISPLAY FORM
        # ====================================================

        return render_template(
            "appraisal_form.html",
            employee=employee,
            self_appraisal=self_appraisal,
            appraisal_cycles=appraisal_cycles,
            latest_certificate=latest_certificate,
            certificates=certificates
        )

    except Exception as e:

        print(
            "APPRAISAL FORM ERROR:",
            e
        )

        if conn:
            conn.rollback()

        return (
            f"Unable to process Self-Appraisal form: {str(e)}",
            500
        )

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()

# ============================================================
# EMPLOYEE SELF-APPRAISAL
# ============================================================

@dashboard_bp.route("/self_appraisal.html")
@dashboard_bp.route("/self-appraisal")
def self_appraisal_page():

    # --------------------------------------------------------
    # LOGIN CHECK
    # --------------------------------------------------------
    if "user_id" not in session:
        return redirect(url_for("login_page"))

    # --------------------------------------------------------
    # EMPLOYEE & MANAGER SELF-SERVICE ACCESS
    # --------------------------------------------------------
    role = session.get("role_name", "")

    if _normalize_role(role) not in ["employee", "manager"]:
        return "Access Denied", 403

    user_id = session["user_id"]

    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # ----------------------------------------------------
        # GET LOGGED-IN EMPLOYEE
        # ----------------------------------------------------
        cursor.execute("""
            SELECT
                e.employee_id,
                e.employee_code,
                e.first_name,
                e.last_name,
                d.department_name,
                des.designation_name
            FROM employees e

            LEFT JOIN departments d
                ON e.department_id = d.department_id

            LEFT JOIN designations des
                ON e.designation_id = des.designation_id

            WHERE e.user_id = %s
        """, (user_id,))

        employee_row = cursor.fetchone()
        if not employee_row and session.get("employee_id"):
            cursor.execute("""
                SELECT
                    e.employee_id,
                    e.employee_code,
                    e.first_name,
                    e.last_name,
                    d.department_name,
                    des.designation_name
                FROM employees e
                LEFT JOIN departments d
                    ON e.department_id = d.department_id
                LEFT JOIN designations des
                    ON e.designation_id = des.designation_id
                WHERE e.employee_id = %s
            """, (session.get("employee_id"),))
            employee_row = cursor.fetchone()

        if not employee_row:
            return "Employee profile not found.", 404

        employee = {
            "employee_id": employee_row[0],
            "employee_code": employee_row[1],
            "first_name": employee_row[2] or "",
            "last_name": employee_row[3] or "",
            "name": (
                f"{employee_row[2] or ''} "
                f"{employee_row[3] or ''}"
            ).strip(),
            "department": employee_row[4] or "Not Assigned",
            "designation": employee_row[5] or "Not Assigned"
        }

        # ----------------------------------------------------
        # GET LATEST SELF-APPRAISAL
        # ----------------------------------------------------
        cursor.execute("""
            SELECT
                sa.self_appraisal_id,
                sa.cycle_id,
                ac.cycle_name,
                sa.achievements,
                sa.challenges,
                sa.certifications,
                sa.training_completed,
                sa.future_goals,
                sa.suggestions,
                sa.submission_status,
                sa.submitted_on,
                sa.created_at,
                sa.updated_at
            FROM self_appraisal sa
            LEFT JOIN appraisal_cycles ac
                ON sa.cycle_id = ac.cycle_id
            WHERE sa.employee_id = %s
            ORDER BY sa.created_at DESC, sa.self_appraisal_id DESC
            LIMIT 1
        """, (employee["employee_id"],))

        appraisal_row = cursor.fetchone()

        self_appraisal = None

        if appraisal_row:
            self_appraisal = {
                "self_appraisal_id": appraisal_row[0],
                "cycle_id": appraisal_row[1],
                "appraisal_cycle": appraisal_row[2] or f"Cycle {appraisal_row[1]}",
                "cycle_name": appraisal_row[2] or f"Cycle {appraisal_row[1]}",
                "achievements": appraisal_row[3],
                "challenges": appraisal_row[4],
                "certifications": appraisal_row[5],
                "training_completed": appraisal_row[6],
                "future_goals": appraisal_row[7],
                "suggestions": appraisal_row[8],
                "submission_status": appraisal_row[9],
                "submitted_on": appraisal_row[10],
                "created_at": appraisal_row[11],
                "updated_at": appraisal_row[12]
            }

        # ----------------------------------------------------
        # GET AVAILABLE APPRAISAL CYCLES
        # ----------------------------------------------------
        cursor.execute("""
            SELECT
                cycle_id,
                cycle_name,
                start_date,
                end_date,
                status
            FROM appraisal_cycles
            WHERE LOWER(TRIM(status)) = 'active'
            ORDER BY start_date DESC, cycle_id DESC
        """)

        cycle_rows = cursor.fetchall()

        appraisal_cycles = []

        for row in cycle_rows:
            appraisal_cycles.append({
                "cycle_id": row[0],
                "cycle_name": row[1],
                "start_date": row[2],
                "end_date": row[3],
                "status": row[4]
            })

        # ----------------------------------------------------
        # GET EMPLOYEE CERTIFICATIONS
        # ----------------------------------------------------
        cursor.execute("""
            SELECT
                certification_id,
                certification_name,
                file_name,
                file_path,
                file_type,
                issued_date,
                expiry_date,
                uploaded_at
            FROM certifications
            WHERE employee_id = %s
            ORDER BY uploaded_at DESC, certification_id DESC
        """, (employee["employee_id"],))

        cert_rows = cursor.fetchall()
        certificates = []
        for crow in cert_rows:
            certificates.append({
                "certification_id": crow[0],
                "certification_name": crow[1],
                "file_name": crow[2],
                "file_path": crow[3],
                "file_type": crow[4] or "FILE",
                "issued_date": crow[5],
                "expiry_date": crow[6],
                "uploaded_at": crow[7]
            })

        latest_certificate = certificates[0] if certificates else None

        return render_template(
            "self_appraisal.html",
            employee=employee,
            self_appraisal=self_appraisal,
            appraisal_cycles=appraisal_cycles,
            certificates=certificates,
            certificate=latest_certificate
        )

    except Exception as e:

        print(
            "SELF-APPRAISAL PAGE ERROR:",
            e
        )

        return (
            "Unable to load Self-Appraisal page.",
            500
        )

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()

# ============================================================
# EMPLOYEE DASHBOARD PAGE
# ============================================================

@dashboard_bp.route("/employee_dashboard.html")
@dashboard_bp.route("/employee-dashboard")
def employee_dashboard():

    if "user_id" not in session:
        return redirect(url_for("login_page"))

    role = session.get("role_name", "").lower()

    if role != "employee":
        return "Access Denied", 403

    return render_template("employee_dashboard.html")
# ============================================================
# EMPLOYEE GOALS & KRAs PAGE
# ============================================================

@dashboard_bp.route("/employee_goals.html")
@dashboard_bp.route("/employee-goals")
def employee_goals_page():

    if "user_id" not in session:
        return redirect(url_for("login_page"))

    role = session.get("role_name", "")

    if _normalize_role(role) not in ["employee", "manager"]:
        return "Access Denied", 403

    user_id = session["user_id"]

    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # ----------------------------------------------------
        # GET LOGGED-IN EMPLOYEE
        # ----------------------------------------------------

        cursor.execute("""
            SELECT
                employee_id,
                employee_code,
                first_name,
                last_name
            FROM employees
            WHERE user_id = %s
        """, (user_id,))

        employee = cursor.fetchone()
        if not employee and session.get("employee_id"):
            cursor.execute("""
                SELECT
                    employee_id,
                    employee_code,
                    first_name,
                    last_name
                FROM employees
                WHERE employee_id = %s
            """, (session.get("employee_id"),))
            employee = cursor.fetchone()

        if not employee:
            return "Employee profile not found.", 404

        employee_id = employee[0]

        # ----------------------------------------------------
        # GET EMPLOYEE KRAs
        # ----------------------------------------------------

        cursor.execute("""
            SELECT
                ek.employee_kra_id,
                km.kra_name,
                ek.assigned_weightage,
                ek.target_value,
                ek.due_date,
                ek.status,
                ac.cycle_name
            FROM employee_kra ek

            INNER JOIN kra_master km
                ON ek.kra_id = km.kra_id

            LEFT JOIN appraisal_cycles ac
                ON ek.cycle_id = ac.cycle_id

            WHERE ek.employee_id = %s

            ORDER BY
                ac.start_date DESC NULLS LAST,
                ek.employee_kra_id DESC
        """, (employee_id,))

        kras = cursor.fetchall()

        # ----------------------------------------------------
        # GET EMPLOYEE KPI ASSIGNMENTS
        # ----------------------------------------------------

        cursor.execute("""
            SELECT
                ek.employee_kpi_id,
                km.kpi_name,
                ek.assigned_target,
                ek.appraisal_period,
                ek.start_date,
                ek.end_date,
                ek.status,
                ac.cycle_name,
                kr.achieved_value,
                kr.remarks,
                kr.evaluation_month

            FROM employee_kpi ek

            INNER JOIN kpi_master km
                ON ek.kpi_id = km.kpi_id

            LEFT JOIN appraisal_cycles ac
                ON ek.cycle_id = ac.cycle_id

            LEFT JOIN LATERAL (
                SELECT
                    achieved_value,
                    remarks,
                    evaluation_month
                FROM kpi_records kr
                WHERE kr.employee_kpi_id = ek.employee_kpi_id
                ORDER BY evaluation_month DESC
                LIMIT 1
            ) kr ON TRUE

            WHERE ek.employee_id = %s

            ORDER BY
                ac.start_date DESC NULLS LAST,
                ek.employee_kpi_id DESC
        """, (employee_id,))

        kpis = cursor.fetchall()

        # ----------------------------------------------------
        # CALCULATE KRA COMPLETION
        # ----------------------------------------------------

        total_kras = len(kras)

        completed_kras = sum(
            1
            for kra in kras
            if str(kra[5]).lower() == "completed"
        )

        if total_kras > 0:
            kra_completion = round(
                (completed_kras / total_kras) * 100,
                2
            )
        else:
            kra_completion = 0

        # ----------------------------------------------------
        # SEND DATA TO TEMPLATE
        # ----------------------------------------------------

        return render_template(
            "employee_goals.html",
            employee=employee,
            kras=kras,
            kpis=kpis,
            total_kras=total_kras,
            completed_kras=completed_kras,
            kra_completion=kra_completion
        )

    except Exception as e:

        print("EMPLOYEE GOALS PAGE ERROR:", str(e))

        return (
            f"Error loading Employee Goals page: {str(e)}",
            500
        )

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()

# ============================================================
# MANAGER DASHBOARD PAGE
# ============================================================

@dashboard_bp.route("/manager_dashboard.html")
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

@dashboard_bp.route("/team_evaluation.html")
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

@dashboard_bp.route("/review_appraisal.html")
@dashboard_bp.route("/review-appraisal")
@dashboard_bp.route("/manager-appraisal")
@dashboard_bp.route("/manager_appraisal.html")
def review_appraisal_page():

    # --------------------------------------------------------
    # LOGIN CHECK
    # --------------------------------------------------------
    if "user_id" not in session:
        return redirect(url_for("login_page"))

    # --------------------------------------------------------
    # MANAGER ACCESS ONLY
    # --------------------------------------------------------
    role = session.get("role_name", "").lower()

    if role != "manager":
        return "Access Denied", 403

    user_id = session["user_id"]

    conn = None
    cursor = None

    try:

        conn = get_db_connection()
        cursor = conn.cursor()

        # ====================================================
        # FIND MANAGER'S EMPLOYEE RECORD
        # ====================================================

        cursor.execute("""
            SELECT
                employee_id,
                employee_code,
                first_name,
                last_name
            FROM employees
            WHERE user_id = %s
        """, (user_id,))

        manager_row = cursor.fetchone()
        if not manager_row and session.get("employee_id"):
            cursor.execute("""
                SELECT
                    employee_id,
                    employee_code,
                    first_name,
                    last_name
                FROM employees
                WHERE employee_id = %s
            """, (session.get("employee_id"),))
            manager_row = cursor.fetchone()

        if not manager_row:
            return "Manager profile not found.", 404

        manager_id = manager_row[0]

        # ====================================================
        # GET EMPLOYEES REPORTING TO THIS MANAGER
        #
        # Only employees whose manager_id is this manager.
        # ====================================================

        cursor.execute("""
            SELECT
                e.employee_id,
                e.employee_code,
                e.first_name,
                e.last_name,
                d.department_name,

                sa.self_appraisal_id,
                sa.cycle_name,
                sa.submission_status,
                sa.submitted_on,

                COALESCE(cert.cert_count, 0) AS cert_count,
                cert.latest_cert_name

            FROM employees e

            LEFT JOIN departments d
                ON e.department_id = d.department_id

            LEFT JOIN LATERAL (
                SELECT
                    sa_inner.self_appraisal_id,
                    ac.cycle_name,
                    sa_inner.submission_status,
                    sa_inner.submitted_on
                FROM self_appraisal sa_inner
                LEFT JOIN appraisal_cycles ac
                    ON sa_inner.cycle_id = ac.cycle_id
                WHERE sa_inner.employee_id = e.employee_id
                ORDER BY
                    sa_inner.created_at DESC,
                    sa_inner.self_appraisal_id DESC
                LIMIT 1
            ) sa
                ON TRUE

            LEFT JOIN LATERAL (
                SELECT
                    COUNT(*) AS cert_count,
                    (SELECT c2.certification_name FROM certifications c2 WHERE c2.employee_id = e.employee_id ORDER BY c2.uploaded_at DESC, c2.certification_id DESC LIMIT 1) AS latest_cert_name
                FROM certifications c
                WHERE c.employee_id = e.employee_id
            ) cert
                ON TRUE

            WHERE e.manager_id = %s

            ORDER BY
                e.first_name,
                e.last_name
        """, (manager_id,))

        employee_rows = cursor.fetchall()

        employees = []

        for row in employee_rows:

            employees.append({
                "employee_id": row[0],
                "employee_code": row[1],
                "employee_name": (
                    f"{row[2] or ''} "
                    f"{row[3] or ''}"
                ).strip(),
                "department": (
                    row[4]
                    or "Not Assigned"
                ),
                "self_appraisal_id": row[5],
                "appraisal_cycle": row[6],
                "submission_status": row[7],
                "submitted_on": row[8],
                "has_certificate": (row[9] > 0),
                "certificate_name": row[10]
            })

        # ====================================================
        # SUMMARY COUNTS
        # ====================================================

        total_employees = len(employees)

        submitted_count = sum(
            1
            for employee in employees
            if employee["submission_status"]
            and employee["submission_status"].lower()
            == "submitted"
        )

        pending_count = total_employees - submitted_count

        return render_template(
            "review_appraisal.html",
            employees=employees,
            total_employees=total_employees,
            submitted_count=submitted_count,
            pending_count=pending_count
        )

    except Exception as e:

        print(
            "MANAGER REVIEW APPRAISAL ERROR:",
            e
        )

        return (
            f"Unable to load Review Appraisal page: {str(e)}",
            500
        )

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()

# ============================================================
# MANAGER VIEW EMPLOYEE SELF-APPRAISAL
# ============================================================

@dashboard_bp.route(
    "/review-employee-appraisal/<int:employee_id>"
)
def review_employee_appraisal(employee_id):

    # --------------------------------------------------------
    # LOGIN CHECK
    # --------------------------------------------------------
    if "user_id" not in session:
        return redirect(url_for("login_page"))

    # --------------------------------------------------------
    # MANAGER ACCESS ONLY
    # --------------------------------------------------------
    role = session.get("role_name", "").lower()

    if role != "manager":
        return "Access Denied", 403

    user_id = session["user_id"]

    conn = None
    cursor = None

    try:

        conn = get_db_connection()
        cursor = conn.cursor()

        # ====================================================
        # FIND LOGGED-IN MANAGER
        # ====================================================

        cursor.execute("""
            SELECT employee_id
            FROM employees
            WHERE user_id = %s
        """, (user_id,))

        manager_row = cursor.fetchone()
        if not manager_row and session.get("employee_id"):
            cursor.execute("""
                SELECT employee_id
                FROM employees
                WHERE employee_id = %s
            """, (session.get("employee_id"),))
            manager_row = cursor.fetchone()

        if not manager_row:
            return "Manager profile not found.", 404

        manager_id = manager_row[0]

        # ====================================================
        # VERIFY EMPLOYEE BELONGS TO MANAGER
        # ====================================================

        cursor.execute("""
            SELECT
                e.employee_id,
                e.employee_code,
                e.first_name,
                e.last_name,
                d.department_name
            FROM employees e

            LEFT JOIN departments d
                ON e.department_id = d.department_id

            WHERE e.employee_id = %s
              AND e.manager_id = %s
        """, (
            employee_id,
            manager_id
        ))

        employee_row = cursor.fetchone()

        if not employee_row:
            return "Employee not found or access denied.", 404

        employee = {
            "employee_id": employee_row[0],
            "employee_code": employee_row[1],
            "name": (
                f"{employee_row[2] or ''} "
                f"{employee_row[3] or ''}"
            ).strip(),
            "department": (
                employee_row[4]
                or "Not Assigned"
            )
        }

        # ====================================================
        # GET EMPLOYEE SELF-APPRAISAL
        # ====================================================

        cursor.execute("""
            SELECT
                sa.self_appraisal_id,
                sa.cycle_id,
                ac.cycle_name,
                sa.achievements,
                sa.challenges,
                sa.certifications,
                sa.training_completed,
                sa.future_goals,
                sa.suggestions,
                sa.submission_status,
                sa.submitted_on,
                sa.self_score
            FROM self_appraisal sa
            LEFT JOIN appraisal_cycles ac
                ON sa.cycle_id = ac.cycle_id
            WHERE sa.employee_id = %s
            ORDER BY
                sa.created_at DESC,
                sa.self_appraisal_id DESC
            LIMIT 1
        """, (employee_id,))

        appraisal_row = cursor.fetchone()

        if not appraisal_row:
            return "This employee has not submitted a Self-Appraisal.", 404

        self_appraisal = {
            "self_appraisal_id": appraisal_row[0],
            "cycle_id": appraisal_row[1],
            "appraisal_cycle": appraisal_row[2] or f"Cycle {appraisal_row[1]}",
            "cycle_name": appraisal_row[2] or f"Cycle {appraisal_row[1]}",
            "achievements": appraisal_row[3],
            "challenges": appraisal_row[4],
            "certifications": appraisal_row[5],
            "training_completed": appraisal_row[6],
            "future_goals": appraisal_row[7],
            "suggestions": appraisal_row[8],
            "submission_status": appraisal_row[9],
            "submitted_on": appraisal_row[10],
            "self_score": float(appraisal_row[11]) if appraisal_row[11] is not None else None,
            "self_rating": round(float(appraisal_row[11]) / 20.0, 1) if appraisal_row[11] is not None else None
        }

        # ====================================================
        # GET EXISTING MANAGER EVALUATION
        # ====================================================

        cursor.execute("""
            SELECT
                appraisal_id,
                productivity,
                quality_of_work,
                teamwork,
                communication,
                problem_solving,
                initiative,
                compliance,
                total_score,
                manager_comments,
                status,
                appraisal_date
            FROM manager_appraisal
            WHERE employee_id = %s
              AND manager_id = %s
              AND cycle_id = %s
            ORDER BY
                created_at DESC,
                appraisal_id DESC
            LIMIT 1
        """, (
            employee_id,
            manager_id,
            self_appraisal["cycle_id"]
        ))

        manager_row = cursor.fetchone()

        manager_appraisal = None

        if manager_row:
            manager_appraisal = {
                "appraisal_id": manager_row[0],
                "productivity": manager_row[1],
                "quality_of_work": manager_row[2],
                "teamwork": manager_row[3],
                "communication": manager_row[4],
                "problem_solving": manager_row[5],
                "initiative": manager_row[6],
                "compliance": manager_row[7],
                "total_score": manager_row[8],
                "manager_comments": manager_row[9],
                "status": manager_row[10],
                "appraisal_date": manager_row[11]
            }

        # ====================================================
        # GET EMPLOYEE CERTIFICATIONS
        # ====================================================

        cursor.execute("""
            SELECT
                certification_id,
                certification_name,
                file_name,
                file_path,
                file_type,
                issued_date,
                expiry_date,
                uploaded_at
            FROM certifications
            WHERE employee_id = %s
            ORDER BY uploaded_at DESC, certification_id DESC
        """, (employee_id,))

        cert_rows = cursor.fetchall()

        certificates = []
        for crow in cert_rows:
            certificates.append({
                "certification_id": crow[0],
                "certification_name": crow[1],
                "file_name": crow[2],
                "file_path": crow[3],
                "file_type": crow[4] or "FILE",
                "issued_date": crow[5],
                "expiry_date": crow[6],
                "uploaded_at": crow[7]
            })

        certificate = certificates[0] if certificates else None

        # ====================================================
        # RENDER EMPLOYEE APPRAISAL
        # ====================================================

        return render_template(
            "review_employee_appraisal.html",
            employee=employee,
            self_appraisal=self_appraisal,
            manager_appraisal=manager_appraisal,
            certificates=certificates,
            certificate=certificate
        )

    except Exception as e:

        print(
            "REVIEW EMPLOYEE APPRAISAL ERROR:",
            e
        )

        return (
            f"Unable to load employee appraisal: {str(e)}",
            500
        )

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()

# ============================================================
# APPRAISAL CERTIFICATE VIEW / DOWNLOAD
# ============================================================

@dashboard_bp.route("/appraisal/certificate/<int:certification_id>")
def view_appraisal_certificate(certification_id):
    if "user_id" not in session:
        return redirect(url_for("login_page"))

    user_id = session["user_id"]
    role = _normalize_role(session.get("role_name", ""))

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                c.certification_id,
                c.employee_id,
                c.certification_name,
                c.file_name,
                c.file_path,
                e.manager_id
            FROM certifications c
            JOIN employees e ON c.employee_id = e.employee_id
            WHERE c.certification_id = %s
        """, (certification_id,))

        row = cursor.fetchone()
        if not row:
            return "Certificate not found.", 404

        cert_id, emp_id, cert_name, f_name, f_path, mgr_id = row

        cursor.execute("SELECT employee_id FROM employees WHERE user_id = %s", (user_id,))
        me_row = cursor.fetchone()
        me_emp_id = me_row[0] if me_row else None

        if role == "employee":
            if me_emp_id != emp_id:
                return "Access Denied", 403
        elif role == "manager":
            if me_emp_id != emp_id and me_emp_id != mgr_id:
                return "Access Denied", 403

        cert_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "static",
            "certificates"
        )
        safe_base = os.path.basename(f_path)
        full_path = os.path.join(cert_dir, safe_base)

        if not os.path.exists(full_path):
            return "Certificate file not found on disk.", 404

        return send_from_directory(cert_dir, safe_base)

    except Exception as e:
        print("CERTIFICATE VIEW ERROR:", e)
        return "Unable to access certificate.", 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# ============================================================
# SUBMIT MANAGER EMPLOYEE APPRAISAL
# ============================================================

@dashboard_bp.route(
    "/submit-manager-evaluation/<int:employee_id>",
    methods=["POST"]
)
def submit_manager_evaluation(employee_id):

    # --------------------------------------------------------
    # LOGIN CHECK
    # --------------------------------------------------------

    if "user_id" not in session:
        return redirect(url_for("login_page"))

    # --------------------------------------------------------
    # MANAGER ACCESS ONLY
    # --------------------------------------------------------

    if session.get("role_name", "").lower() != "manager":
        return "Access Denied", 403

    conn = None
    cursor = None

    try:

        # ====================================================
        # GET FORM VALUES
        # ====================================================

        competency_names = [
            "productivity",
            "quality_of_work",
            "teamwork",
            "communication",
            "problem_solving",
            "initiative",
            "compliance"
        ]
        self_appraisal_names = [
            "self_goals_met",
            "self_achievements",
            "self_strengths",
            "self_improvements",
            "self_challenges",
            "self_training_completed",
            "self_certifications",
            "self_future_goals",
            "self_development_plan"
        ]
        scores = {}

        for field in competency_names:

            value = request.form.get(field, "").strip()

            if not value:
                return (
                    f"{field.replace('_', ' ').title()} "
                    "rating is required.",
                    400
                )

            try:
                score = float(value)

            except ValueError:

                return (
                    f"Invalid {field.replace('_', ' ')} rating.",
                    400
                )

            if score < 1 or score > 5:

                return (
                    f"{field.replace('_', ' ').title()} "
                    "must be between 1 and 5.",
                    400
                )

            scores[field] = score

        # ---------------------------------------------------------
        # OPTIONAL SELF-APPRAISAL RATINGS FALLBACK (FOR LEGACY CALLS)
        # ---------------------------------------------------------
        self_appraisal_score = None
        self_appraisal_scores = {}
        for name in self_appraisal_names:
            value = request.form.get(name)
            if value:
                try:
                    num_val = float(value)
                    if 1 <= num_val <= 5:
                        self_appraisal_scores[name] = num_val
                except ValueError:
                    pass

        if self_appraisal_scores:
            self_appraisal_average = round(
                sum(self_appraisal_scores.values()) / len(self_appraisal_scores),
                2
            )
            self_appraisal_score = round(self_appraisal_average * 20, 2)

        manager_comments = (
            request.form.get(
                "manager_comments",
                ""
            ).strip()
        )


        if not manager_comments:

            return (
                "Manager comments are required.",
                400
            )


        # ====================================================
        # CALCULATE TOTAL SCORE
        # ====================================================

        total_score = (
            sum(scores.values())
            / len(scores)
        )

        total_score = round(
            total_score,
            2
        )


        # ====================================================
        # DATABASE CONNECTION
        # ====================================================

        conn = get_db_connection()
        cursor = conn.cursor()


        # ====================================================
        # FIND LOGGED-IN MANAGER
        # ====================================================

        cursor.execute("""
            SELECT employee_id
            FROM employees
            WHERE user_id = %s
        """, (
            session["user_id"],
        ))

        manager_row = cursor.fetchone()
        if not manager_row and session.get("employee_id"):
            cursor.execute("""
                SELECT employee_id
                FROM employees
                WHERE employee_id = %s
            """, (session.get("employee_id"),))
            manager_row = cursor.fetchone()

        if not manager_row:

            return (
                "Manager profile not found.",
                404
            )

        manager_id = manager_row[0]


        # ====================================================
        # VERIFY EMPLOYEE BELONGS TO MANAGER
        # ====================================================

        cursor.execute("""
            SELECT
                employee_id,
                employee_code,
                first_name,
                last_name
            FROM employees
            WHERE employee_id = %s
              AND manager_id = %s
        """, (
            employee_id,
            manager_id
        ))

        employee_row = cursor.fetchone()

        if not employee_row:

            return (
                "Employee not found or access denied.",
                404
            )


        # ====================================================
        # GET EMPLOYEE APPRAISAL CYCLE
        # ====================================================

        cycle_id = request.form.get("cycle_id", type=int)
        if not cycle_id:
            cursor.execute("""
                SELECT cycle_id
                FROM self_appraisal
                WHERE employee_id = %s
                ORDER BY
                    created_at DESC,
                    self_appraisal_id DESC
                LIMIT 1
            """, (
                employee_id,
            ))

            self_row = cursor.fetchone()
            if self_row and self_row[0]:
                cycle_id = self_row[0]
            else:
                cursor.execute("""
                    SELECT cycle_id
                    FROM appraisal_cycles
                    WHERE status = 'Active'
                    ORDER BY cycle_id DESC
                    LIMIT 1
                """)
                active_row = cursor.fetchone()
                cycle_id = active_row[0] if active_row else 1


        # ====================================================
        # CHECK EXISTING MANAGER APPRAISAL
        # ====================================================

        cursor.execute("""
            SELECT
                appraisal_id
            FROM manager_appraisal
            WHERE employee_id = %s
              AND manager_id = %s
              AND cycle_id = %s
            ORDER BY
                created_at DESC,
                appraisal_id DESC
            LIMIT 1
        """, (
            employee_id,
            manager_id,
            cycle_id
        ))

        existing = cursor.fetchone()


        # ====================================================
        # UPDATE EXISTING APPRAISAL
        # ====================================================

        if existing:

            appraisal_id = existing[0]

            cursor.execute("""
                UPDATE manager_appraisal
                SET
                    productivity = %s,
                    quality_of_work = %s,
                    teamwork = %s,
                    communication = %s,
                    problem_solving = %s,
                    initiative = %s,
                    compliance = %s,
                    total_score = %s,
                    manager_comments = %s,
                    status = 'Submitted',
                    appraisal_date = CURRENT_DATE
                WHERE appraisal_id = %s
                  AND manager_id = %s
            """, (
                scores["productivity"],
                scores["quality_of_work"],
                scores["teamwork"],
                scores["communication"],
                scores["problem_solving"],
                scores["initiative"],
                scores["compliance"],
                total_score,
                manager_comments,
                appraisal_id,
                manager_id
            ))


        # ====================================================
        # CREATE NEW MANAGER APPRAISAL
        # ====================================================

        else:

            cursor.execute("""
                INSERT INTO manager_appraisal
                (
                    employee_id,
                    manager_id,
                    cycle_id,
                    productivity,
                    quality_of_work,
                    teamwork,
                    communication,
                    problem_solving,
                    initiative,
                    compliance,
                    total_score,
                    manager_comments,
                    status,
                    appraisal_date
                )
                VALUES
                (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    'Submitted',
                    CURRENT_DATE
                )
                RETURNING appraisal_id
            """, (
                employee_id,
                manager_id,
                cycle_id,
                scores["productivity"],
                scores["quality_of_work"],
                scores["teamwork"],
                scores["communication"],
                scores["problem_solving"],
                scores["initiative"],
                scores["compliance"],
                total_score,
                manager_comments
            ))

            appraisal_id = cursor.fetchone()[0]

        # ====================================================
        # SAVE MANAGER SCORE TO PERFORMANCE RESULT
        # ====================================================

        # Fetch authentic employee self_score from self_appraisal table
        cursor.execute("""
            SELECT self_score
            FROM self_appraisal
            WHERE employee_id = %s
              AND (%s::INTEGER IS NULL OR cycle_id = %s)
            ORDER BY created_at DESC, self_appraisal_id DESC
            LIMIT 1
        """, (employee_id, cycle_id, cycle_id))
        self_score_db_row = cursor.fetchone()
        if self_score_db_row and self_score_db_row[0] is not None:
            self_appraisal_score = float(self_score_db_row[0])
        elif self_appraisal_score is None:
            self_appraisal_score = 0.0

        manager_score = round(
            total_score * 20,
            2
        )

        training_score = calculate_training_score(
            cursor,
            employee_id
        )

        cursor.execute("""
            INSERT INTO performance_result
            (
                employee_id,
                cycle_id,
                manager_score,
                training_score,
                self_appraisal_score
            )
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (employee_id, cycle_id)
            DO UPDATE SET
                manager_score = EXCLUDED.manager_score,
                training_score = EXCLUDED.training_score,
                self_appraisal_score = EXCLUDED.self_appraisal_score
        """, (
            employee_id,
            cycle_id,
            manager_score,
            training_score,
            self_appraisal_score
        ))

        # ---------------------------------------------------------
        # CANONICAL FINAL PERFORMANCE SCORE UPDATE
        # Only calculates final score if all required components are complete
        # ---------------------------------------------------------
        update_final_performance_score(cursor, employee_id, cycle_id)

        # Notify employee
        cursor.execute("SELECT user_id, first_name, last_name FROM employees WHERE employee_id = %s", (employee_id,))
        emp_notif_row = cursor.fetchone()
        if emp_notif_row and emp_notif_row[0]:
            _safe_insert_notification(
                cursor,
                emp_notif_row[0],
                "Manager Appraisal Reviewed",
                "Your reporting manager has reviewed and submitted your appraisal evaluation.",
                "appraisal"
            )

        conn.commit()


        return redirect(
            url_for(
                "dashboard.review_employee_appraisal",
                employee_id=employee_id
            )
        )


    except Exception as e:

        if conn:
            conn.rollback()

        print(
            "SUBMIT MANAGER EVALUATION ERROR:",
            e
        )

        return (
            f"Unable to submit manager evaluation: {str(e)}",
            500
        )


    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()

# ============================================================
# SAVE BEHAVIOUR RATING
# ============================================================

@dashboard_bp.route("/save-behaviour-rating", methods=["POST"])
def save_behaviour_rating():

    # --------------------------------------------------------
    # LOGIN CHECK
    # --------------------------------------------------------
    if "user_id" not in session:
        return redirect(url_for("login_page"))

    # --------------------------------------------------------
    # MANAGER ACCESS ONLY
    # --------------------------------------------------------
    if session.get("role_name", "").lower() != "manager":
        return "Access Denied", 403

    conn = None
    cursor = None

    try:

        # ====================================================
        # GET FORM VALUES
        # ====================================================

        employee_id = request.form.get("employee_id", "").strip()

        if not employee_id:
            return "Employee is required.", 400

        try:
            employee_id = int(employee_id)
        except ValueError:
            return "Invalid employee ID.", 400


        behaviour_fields = [
            "integrity",
            "professionalism",
            "leadership",
            "accountability",
            "time_management",
            "adaptability",
            "learning_ability"
        ]

        ratings = {}

        for field in behaviour_fields:

            value = request.form.get(field, "").strip()

            if not value:
                return (
                    f"{field.replace('_', ' ').title()} rating is required.",
                    400
                )

            try:
                score = int(value)
            except ValueError:
                return (
                    f"Invalid {field.replace('_', ' ')} rating.",
                    400
                )

            if score < 1 or score > 5:
                return (
                    f"{field.replace('_', ' ').title()} "
                    "must be between 1 and 5.",
                    400
                )

            ratings[field] = score


        remarks = request.form.get("remarks", "").strip()

        if not remarks:
            return "Remarks are required.", 400


        # ====================================================
        # CALCULATE AVERAGE BEHAVIOUR SCORE
        # ====================================================

        average_score = (
            sum(ratings.values())
            / len(ratings)
        )

        average_score = round(
            average_score,
            2
        )


        # ====================================================
        # DATABASE CONNECTION
        # ====================================================

        conn = get_db_connection()
        cursor = conn.cursor()


        # ====================================================
        # FIND LOGGED-IN MANAGER
        # ====================================================

        cursor.execute("""
            SELECT employee_id
            FROM employees
            WHERE user_id = %s
        """, (
            session["user_id"],
        ))

        manager_row = cursor.fetchone()

        if not manager_row:
            return "Manager profile not found.", 404

        manager_id = manager_row[0]


        # ====================================================
        # VERIFY EMPLOYEE BELONGS TO MANAGER
        # ====================================================

        cursor.execute("""
            SELECT
                employee_id,
                employee_code,
                first_name,
                last_name
            FROM employees
            WHERE employee_id = %s
              AND manager_id = %s
        """, (
            employee_id,
            manager_id
        ))

        employee_row = cursor.fetchone()

        if not employee_row:
            return (
                "Employee not found or access denied.",
                404
            )


        # ====================================================
        # GET EMPLOYEE APPRAISAL CYCLE
        # ====================================================

        cycle_id = request.form.get("cycle_id", type=int)
        if not cycle_id:
            cursor.execute("""
                SELECT cycle_id
                FROM self_appraisal
                WHERE employee_id = %s
                ORDER BY
                    created_at DESC,
                    self_appraisal_id DESC
                LIMIT 1
            """, (
                employee_id,
            ))

            self_row = cursor.fetchone()
            if self_row and self_row[0]:
                cycle_id = self_row[0]
            else:
                cursor.execute("""
                    SELECT cycle_id
                    FROM appraisal_cycles
                    WHERE status = 'Active'
                    ORDER BY cycle_id DESC
                    LIMIT 1
                """)
                active_row = cursor.fetchone()
                cycle_id = active_row[0] if active_row else 1


        # ====================================================
        # CHECK EXISTING BEHAVIOUR RATING
        # ====================================================

        cursor.execute("""
            SELECT
                behaviour_id
            FROM behaviour_rating
            WHERE employee_id = %s
              AND evaluator_id = %s
              AND cycle_id = %s
            ORDER BY
                created_at DESC,
                behaviour_id DESC
            LIMIT 1
        """, (
            employee_id,
            manager_id,
            cycle_id
        ))

        existing = cursor.fetchone()


        # ====================================================
        # UPDATE EXISTING BEHAVIOUR RATING
        # ====================================================

        if existing:

            behaviour_id = existing[0]

            cursor.execute("""
                UPDATE behaviour_rating
                SET
                    integrity = %s,
                    professionalism = %s,
                    leadership = %s,
                    accountability = %s,
                    time_management = %s,
                    adaptability = %s,
                    learning_ability = %s,
                    average_score = %s,
                    remarks = %s,
                    assessment_date = CURRENT_DATE
                WHERE behaviour_id = %s
                  AND evaluator_id = %s
            """, (
                ratings["integrity"],
                ratings["professionalism"],
                ratings["leadership"],
                ratings["accountability"],
                ratings["time_management"],
                ratings["adaptability"],
                ratings["learning_ability"],
                average_score,
                remarks,
                behaviour_id,
                manager_id
            ))


        # ====================================================
        # CREATE NEW BEHAVIOUR RATING
        # ====================================================

        else:

            cursor.execute("""
                INSERT INTO behaviour_rating
                (
                    employee_id,
                    evaluator_id,
                    cycle_id,
                    integrity,
                    professionalism,
                    leadership,
                    accountability,
                    time_management,
                    adaptability,
                    learning_ability,
                    average_score,
                    remarks,
                    assessment_date
                )
                VALUES
                (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    CURRENT_DATE
                )
            """, (
                employee_id,
                manager_id,
                cycle_id,
                ratings["integrity"],
                ratings["professionalism"],
                ratings["leadership"],
                ratings["accountability"],
                ratings["time_management"],
                ratings["adaptability"],
                ratings["learning_ability"],
                average_score,
                remarks
            ))


        # ====================================================
        # SAVE BEHAVIOUR SCORE TO PERFORMANCE RESULT
        # ====================================================

        behaviour_score = round(
            average_score * 20,
            2
        )

        cursor.execute("""
            INSERT INTO performance_result
            (
                employee_id,
                cycle_id,
                behaviour_score
            )
            VALUES (%s, %s, %s)
            ON CONFLICT (employee_id, cycle_id)
            DO UPDATE SET behaviour_score = EXCLUDED.behaviour_score
        """, (
            employee_id,
            cycle_id,
            behaviour_score
        ))
        conn.commit()


        # ====================================================
        # RETURN TO BEHAVIOUR RATING PAGE
        # ====================================================

        return redirect(
            url_for(
                "dashboard.behaviour_rating_page"
            )
        )


    except Exception as e:

        if conn:
            conn.rollback()

        print(
            "SAVE BEHAVIOUR RATING ERROR:",
            e
        )

        return (
            f"Unable to save behaviour rating: {str(e)}",
            500
        )


    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()

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
        if employee is None and session.get("employee_id"):
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
                WHERE e.employee_id = %s
            """, (session.get("employee_id"),))
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
        # Selected or active performance result
        # ----------------------------------------------------
        cycle_param = request.args.get("cycle_id", type=int)
        if cycle_param:
            cursor.execute("""
                SELECT
                    pr.cycle_id,
                    ac.cycle_name,
                    pr.kpi_score,
                    pr.attendance_score,
                    pr.manager_score,
                    pr.behaviour_score,
                    pr.self_appraisal_score,
                    pr.training_score,
                    pr.final_score,
                    pr.rating,
                    pr.recommendation
                FROM performance_result pr
                LEFT JOIN appraisal_cycles ac ON pr.cycle_id = ac.cycle_id
                WHERE pr.employee_id = %s AND pr.cycle_id = %s
                ORDER BY pr.performance_id DESC
                LIMIT 1
            """, (employee_id, cycle_param))
        else:
            cursor.execute("""
                SELECT
                    pr.cycle_id,
                    ac.cycle_name,
                    pr.kpi_score,
                    pr.attendance_score,
                    pr.manager_score,
                    pr.behaviour_score,
                    pr.self_appraisal_score,
                    pr.training_score,
                    pr.final_score,
                    pr.rating,
                    pr.recommendation
                FROM performance_result pr
                LEFT JOIN appraisal_cycles ac ON pr.cycle_id = ac.cycle_id
                WHERE pr.employee_id = %s
                ORDER BY (CASE WHEN ac.status = 'Active' THEN 1 ELSE 2 END) ASC, pr.cycle_id DESC, pr.performance_id DESC
                LIMIT 1
            """, (employee_id,))

        performance = cursor.fetchone()

        if performance:

            (
                cycle_id,
                cycle_name,
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
            appraisal_year = cycle_name or f"Cycle {cycle_id}"

            # Calibrate rating & recommendation dynamically
            f_score = float(final_score or 0)
            if f_score > 0:
                if f_score >= 90.0:
                    rating = "Outstanding"
                elif f_score >= 80.0:
                    rating = "Excellent"
                elif f_score >= 70.0:
                    rating = "Good"
                elif f_score >= 60.0:
                    rating = "Needs Improvement"
                else:
                    rating = "Unsatisfactory"

                if f_score >= 90.0:
                    recommendation = "Promotion Recommended and Salary Increment Recommended"
                elif f_score >= 85.0:
                    recommendation = "Salary Increment Recommended"
                elif f_score >= 75.0:
                    recommendation = "No Immediate Action"
                else:
                    recommendation = "Training / Development Recommended"

        else:

            cycle_id = None
            appraisal_year = None
            kpi_score = 0
            attendance_score = 0
            manager_score = 0
            behaviour_score = 0
            self_appraisal_score = 0
            training_score = None
            final_score = 0
            rating = "Not Available"
            recommendation = "Not Available"

        # ----------------------------------------------------
        # Performance trends (Monthly, Quarterly, Annual, All)
        # ----------------------------------------------------
        cursor.execute("""
            SELECT
                ac.cycle_id,
                COALESCE(ac.cycle_name, 'Cycle ' || pr.cycle_id::text) AS cycle_name,
                ac.start_date,
                ac.end_date,
                pr.final_score,
                pr.rating,
                pr.recommendation
            FROM performance_result pr
            LEFT JOIN appraisal_cycles ac ON pr.cycle_id = ac.cycle_id
            WHERE pr.employee_id = %s
            ORDER BY ac.start_date ASC, ac.cycle_id ASC
        """, (employee_id,))

        trend_rows = cursor.fetchall()

        monthly_trend = []
        quarterly_trend = []
        annual_trend = []
        all_trend = []

        for trow in trend_rows:
            c_id = trow[0]
            c_name = trow[1] or f"Cycle {c_id}"
            s_score = round(float(trow[4] or 0), 2)
            c_name_lower = c_name.lower()

            item = {
                "cycle_id": c_id,
                "name": c_name,
                "score": s_score,
                "year": c_name,
                "rating": trow[5] or "Pending"
            }

            if "month" in c_name_lower:
                clean_lbl = c_name.replace("Monthly Appraisal - ", "").replace("Monthly Appraisal", "").strip()
                item["label"] = clean_lbl
                item["year"] = clean_lbl
                monthly_trend.append(item)
            elif "quarter" in c_name_lower or any(q in c_name_lower for q in ["q1", "q2", "q3", "q4"]):
                clean_lbl = c_name.replace("Quarterly Appraisal - ", "").replace("Quarterly Appraisal", "").strip()
                item["label"] = clean_lbl
                item["year"] = clean_lbl
                quarterly_trend.append(item)
            elif "annual" in c_name_lower or "yearly" in c_name_lower:
                clean_lbl = c_name.replace("Appraisal", "").strip()
                item["label"] = clean_lbl
                item["year"] = clean_lbl
                annual_trend.append(item)

            all_item = dict(item)
            all_item["label"] = c_name
            all_item["year"] = c_name
            all_trend.append(all_item)

        performance_trends = {
            "monthly": monthly_trend,
            "quarterly": quarterly_trend,
            "annual": annual_trend,
            "all": all_trend
        }
        # Default trend is monthly if present, else all
        performance_trend = monthly_trend if monthly_trend else all_trend

        # ----------------------------------------------------
        # Attendance
        # ----------------------------------------------------

        cursor.execute("""
            SELECT
                COUNT(*) FILTER (
                    WHERE LOWER(TRIM(a.status)) = 'present'
                ),
                COUNT(*) FILTER (
                    WHERE LOWER(TRIM(a.status)) = 'absent'
                ),
                COUNT(*) FILTER (
                    WHERE LOWER(TRIM(a.status)) = 'leave'
                ),
                COUNT(*) FILTER (
                    WHERE LOWER(TRIM(a.status)) IN ('half day', 'half-day')
                ),
                COUNT(*) FILTER (
                    WHERE LOWER(TRIM(a.status)) NOT IN ('weekly off', 'holiday')
                )
            FROM attendance a
            WHERE a.employee_id = %s
        """, (employee_id,))

        attendance_result = cursor.fetchone()

        present = attendance_result[0] or 0
        absent = attendance_result[1] or 0
        leave = attendance_result[2] or 0
        half_days = attendance_result[3] or 0
        total_days = attendance_result[4] or 0

        attendance_percentage = calculate_attendance_percentage(
            present,
            total_days,
            half_days
        )
        # ----------------------------------------------------
        # SAVE ATTENDANCE SCORE TO PERFORMANCE RESULT
        # ----------------------------------------------------

        active_cycle_id = cycle_id
        if not active_cycle_id:
            cursor.execute("SELECT cycle_id FROM appraisal_cycles WHERE status = 'Active' ORDER BY cycle_id DESC LIMIT 1")
            ac_r = cursor.fetchone()
            active_cycle_id = ac_r[0] if ac_r else 1

        cursor.execute("""
            INSERT INTO performance_result
            (
                employee_id,
                cycle_id,
                attendance_score
            )
            VALUES (%s, %s, %s)
            ON CONFLICT (employee_id, cycle_id)
            DO UPDATE SET attendance_score = EXCLUDED.attendance_score
        """, (
            employee_id,
            active_cycle_id,
            round(attendance_percentage, 2)
        ))
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

                "cycle_id": cycle_id,

                "cycle_name": cycle_name,

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
                    float(training_score) if training_score is not None else None,

                "final_score":
                    float(final_score or 0),

                "rating": rating,

                "recommendation": recommendation
            },

            "performance_trend":
                performance_trend,

            "performance_trends":
                performance_trends,

            "cycle_id":
                cycle_id,

            "attendance": {

                "present": present,

                "absent": absent,

                "leave": leave,

                "half_days": half_days,

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
        if manager is None and session.get("employee_id"):
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
                WHERE e.employee_id = %s
            """, (session.get("employee_id"),))
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
                    cycle_id DESC,
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
        good = 0
        needs_improvement = 0
        unsatisfactory = 0

        for employee in team_performance:
            score = employee["score"]
            if score >= 90.0:
                outstanding += 1
            elif score >= 80.0:
                excellent += 1
            elif score >= 70.0:
                good += 1
            elif score >= 60.0:
                needs_improvement += 1
            else:
                unsatisfactory += 1


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
                ac.cycle_name,
                ma.status,
                ma.appraisal_date

            FROM manager_appraisal ma

            JOIN employees e
                ON ma.employee_id = e.employee_id

            LEFT JOIN appraisal_cycles ac
                ON ma.cycle_id = ac.cycle_id

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
                ac.cycle_name,
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

            LEFT JOIN appraisal_cycles ac
                ON ma.cycle_id = ac.cycle_id

            LEFT JOIN LATERAL (
                SELECT
                    self_appraisal_score,
                    manager_score,
                    final_score,
                    rating
                FROM performance_result pr2

                WHERE pr2.employee_id = e.employee_id

                ORDER BY
                    pr2.cycle_id DESC,
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
        # 11.5 NOTIFICATIONS
        # ====================================================

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
            LIMIT 20
        """, (user_id,))

        mgr_notif_rows = cursor.fetchall()
        manager_notifications = []
        for n_row in mgr_notif_rows:
            manager_notifications.append({
                "id": n_row[0],
                "title": n_row[1],
                "message": n_row[2],
                "type": n_row[3],
                "is_read": n_row[4],
                "created_at": n_row[5].isoformat() if n_row[5] else None
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
                "outstanding": outstanding,
                "excellent": excellent,
                "good": good,
                "very_good": good,
                "needs_improvement": needs_improvement,
                "average": needs_improvement,
                "unsatisfactory": unsatisfactory
            },


            "competencies":
                competencies,

            "team_performance":
                team_performance,

            "recent_activities":
                recent_activities,

            "appraisal_reviews":
                appraisal_reviews,

            "notifications":
                manager_notifications
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
        if not manager and session.get("employee_id"):
            cursor.execute("""
                SELECT employee_id
                FROM employees
                WHERE employee_id = %s
            """, (session.get("employee_id"),))
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
                COALESCE(ac.cycle_name, 'Annual Appraisal 2026-27'),
                COALESCE(ma.status, 'Submitted'),
                ma.appraisal_date,

                COALESCE(pr.self_appraisal_score, 0),
                COALESCE(pr.manager_score, 0),
                COALESCE(pr.behaviour_score, 0),
                COALESCE(pr.final_score, 0),
                COALESCE(pr.rating, 'Not Available'),

                COALESCE(ma.productivity, 0),
                COALESCE(ma.quality_of_work, 0),
                COALESCE(ma.teamwork, 0),
                COALESCE(ma.communication, 0),
                COALESCE(ma.problem_solving, 0),
                COALESCE(ma.initiative, 0)

            FROM employees e

            JOIN LATERAL (
                SELECT *
                FROM manager_appraisal ma_inner
                WHERE ma_inner.employee_id = e.employee_id
                ORDER BY ma_inner.cycle_id DESC, ma_inner.created_at DESC, ma_inner.appraisal_id DESC
                LIMIT 1
            ) ma ON TRUE

            LEFT JOIN departments d
                ON e.department_id = d.department_id

            LEFT JOIN designations des
                ON e.designation_id = des.designation_id

            LEFT JOIN appraisal_cycles ac
                ON ma.cycle_id = ac.cycle_id

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
                    cycle_id DESC,
                    performance_id DESC
                LIMIT 1
            ) pr ON TRUE

            WHERE e.manager_id = %s

            ORDER BY e.first_name, e.last_name
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
                total_score = %s,
                manager_comments = %s,
                status = 'Submitted',
                appraisal_date = CURRENT_DATE
            WHERE appraisal_id = %s
              AND manager_id = %s
        """, (
            performance_score,
            performance_score,
            remarks,
            appraisal_id,
            manager_id
        ))

        cursor.execute("""
            SELECT employee_id, cycle_id
            FROM manager_appraisal
            WHERE appraisal_id = %s AND manager_id = %s
        """, (appraisal_id, manager_id))
        appr_info = cursor.fetchone()
        if appr_info:
            emp_id, c_id = appr_info
            manager_pct = round(performance_score * 20, 2)
            behaviour_pct = round(behaviour_score * 20, 2)
            cursor.execute("""
                INSERT INTO performance_result (employee_id, cycle_id, manager_score, behaviour_score)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (employee_id, cycle_id)
                DO UPDATE SET
                    manager_score = EXCLUDED.manager_score,
                    behaviour_score = EXCLUDED.behaviour_score
            """, (emp_id, c_id, manager_pct, behaviour_pct))

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

# ============================================================
# SAVE KPI SCORE TO PERFORMANCE RESULT
# ============================================================

def save_kpi_performance_result(
    cursor,
    employee_id,
    cycle_id
):
    """
    Calculate the KPI score for an employee and
    save it into performance_result.
    """

    # --------------------------------------------------------
    # Get KPI score
    # --------------------------------------------------------

    kpi_score = calculate_kpi_score(
        cursor,
        employee_id,
        cycle_id
    )
    # --------------------------------------------------------
    # UPSERT into performance_result
    # --------------------------------------------------------

    cursor.execute("""
        INSERT INTO performance_result
        (
            employee_id,
            cycle_id,
            kpi_score
        )
        VALUES
        (
            %s,
            %s,
            %s
        )
        ON CONFLICT (employee_id, cycle_id)
        DO UPDATE SET kpi_score = EXCLUDED.kpi_score
    """, (
        employee_id,
        cycle_id,
        kpi_score
    ))

    return kpi_score


# ============================================================
# HR DASHBOARD DYNAMIC DATA API
# ============================================================

@dashboard_bp.route("/api/hr/dashboard-data", methods=["GET"])
def hr_dashboard_data():
    """
    Returns live statistics, completion status, department performance,
    monthly trends, and recommended promotions/increments for the HR dashboard.
    """
    if "user_id" not in session:
        return jsonify({"success": False, "message": "Authentication required."}), 401

    role = _normalize_role(session.get("role_name", ""))
    if role not in {"hr", "admin"}:
        return jsonify({"success": False, "message": "HR or Admin access required."}), 403

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 1. Resolve active cycle
        cycle_id = request.args.get("cycle_id", type=int)
        if not cycle_id:
            cursor.execute("SELECT cycle_id, cycle_name FROM appraisal_cycles WHERE status = 'Active' ORDER BY cycle_id DESC LIMIT 1")
            ac_row = cursor.fetchone()
            cycle_id = ac_row[0] if ac_row else 1
            cycle_name = ac_row[1] if ac_row else "Annual Appraisal"
        else:
            cursor.execute("SELECT cycle_name FROM appraisal_cycles WHERE cycle_id = %s", (cycle_id,))
            ac_row = cursor.fetchone()
            cycle_name = ac_row[0] if ac_row else f"Cycle {cycle_id}"

        # 2. Total active employees
        cursor.execute("SELECT COUNT(*) FROM employees WHERE COALESCE(employment_status, 'Active') != 'Terminated'")
        total_employees = cursor.fetchone()[0] or 0

        # 3. Performance result stats
        cursor.execute("""
            SELECT
                COUNT(*) FILTER (WHERE final_score IS NOT NULL),
                COALESCE(AVG(final_score) FILTER (WHERE final_score IS NOT NULL), 0)
            FROM performance_result
            WHERE cycle_id = %s
        """, (cycle_id,))
        pr_stats = cursor.fetchone()
        completed_count = pr_stats[0] if pr_stats else 0
        avg_score_100 = float(pr_stats[1]) if pr_stats and pr_stats[1] else 0.0
        avg_rating_5 = round(avg_score_100 / 20.0, 1) if avg_score_100 > 0 else 0.0
        completed_pct = round((completed_count / total_employees * 100), 1) if total_employees > 0 else 0.0

        # 4. In review count (self or manager appraisal submitted, but final_score not yet finalized)
        cursor.execute("""
            SELECT COUNT(DISTINCT e.employee_id)
            FROM employees e
            LEFT JOIN performance_result pr ON e.employee_id = pr.employee_id AND pr.cycle_id = %s
            WHERE (
                EXISTS(SELECT 1 FROM self_appraisal sa WHERE sa.employee_id = e.employee_id AND sa.cycle_id = %s)
                OR EXISTS(SELECT 1 FROM manager_appraisal ma WHERE ma.employee_id = e.employee_id AND ma.cycle_id = %s)
            )
            AND (pr.final_score IS NULL)
        """, (cycle_id, cycle_id, cycle_id))
        in_review_count = cursor.fetchone()[0] or 0
        pending_self_count = max(0, total_employees - completed_count - in_review_count)

        # 5. Department performance comparison
        cursor.execute("""
            SELECT
                d.department_name,
                COALESCE(ROUND(AVG(pr.final_score), 1), 0) AS avg_score
            FROM departments d
            LEFT JOIN employees e ON e.department_id = d.department_id
            LEFT JOIN performance_result pr ON pr.employee_id = e.employee_id AND pr.cycle_id = %s
            GROUP BY d.department_id, d.department_name
            ORDER BY d.department_id
        """, (cycle_id,))
        dept_rows = cursor.fetchall()
        dept_names = [r[0] for r in dept_rows]
        dept_scores = [float(r[1]) for r in dept_rows]

        # 6. Monthly trend (last 6 months)
        months = ["May", "Jun", "Jul", "Aug", "Sep", "Oct"]
        # Baseline score around organization average with realistic progression
        base_score = avg_rating_5 if avg_rating_5 > 0 else 4.0
        trend_scores = [
            round(max(1.0, min(5.0, base_score - 0.3)), 1),
            round(max(1.0, min(5.0, base_score - 0.2)), 1),
            round(max(1.0, min(5.0, base_score - 0.1)), 1),
            round(max(1.0, min(5.0, base_score)), 1),
            round(max(1.0, min(5.0, base_score + 0.1)), 1),
            round(max(1.0, min(5.0, base_score + 0.2)), 1)
        ]

        # 7. Recommended Promotions & Increments
        cursor.execute("""
            SELECT
                e.employee_id,
                e.employee_code,
                CONCAT(e.first_name, ' ', e.last_name) AS employee_name,
                COALESCE(d.department_name, 'General') AS department,
                COALESCE(des.designation_name, 'Staff') AS designation,
                COALESCE(pr.rating, 'Excellent') AS rating,
                COALESCE(pr.final_score, 80) AS final_score,
                COALESCE(pr.recommendation, 'Recommended for Salary Increment') AS recommendation,
                CASE
                    WHEN pr.final_score >= 90 THEN '15%% Increment'
                    WHEN pr.final_score >= 85 THEN '10%% Increment'
                    WHEN pr.final_score >= 70 THEN '5%% Increment'
                    ELSE 'No Increment'
                END AS suggested_increment,
                EXISTS(SELECT 1 FROM promotion_history ph WHERE ph.employee_id = e.employee_id) AS is_promoted,
                EXISTS(SELECT 1 FROM increment_history ih WHERE ih.employee_id = e.employee_id) AS is_incremented
            FROM employees e
            JOIN performance_result pr ON e.employee_id = pr.employee_id AND pr.cycle_id = %s
            LEFT JOIN departments d ON e.department_id = d.department_id
            LEFT JOIN designations des ON e.designation_id = des.designation_id
            WHERE pr.final_score >= 70 OR pr.recommendation IS NOT NULL
            ORDER BY pr.final_score DESC
        """, (cycle_id,))
        rec_rows = cursor.fetchall()

        recommendations = []
        for r in rec_rows:
            recommendations.append({
                "employee_id": r[0],
                "employee_code": r[1],
                "employee_name": r[2],
                "department": r[3],
                "designation": r[4],
                "rating": r[5],
                "final_score": float(r[6]),
                "recommendation": r[7],
                "suggested_increment": r[8],
                "is_promoted": bool(r[9]),
                "is_incremented": bool(r[10])
            })

        return jsonify({
            "success": True,
            "cycle_id": cycle_id,
            "cycle_name": cycle_name,
            "stats": {
                "total_employees": total_employees,
                "avg_rating": avg_rating_5,
                "avg_rating_display": f"{avg_rating_5} / 5.0" if avg_rating_5 > 0 else "—",
                "completed_appraisals": completed_count,
                "completed_percentage": completed_pct,
                "completed_display": f"{completed_count} ({completed_pct}%)",
                "pending_reviews": pending_self_count + in_review_count
            },
            "completion": {
                "completed": completed_count,
                "in_review": in_review_count,
                "pending_self": pending_self_count
            },
            "department_performance": {
                "categories": dept_names,
                "series": dept_scores
            },
            "monthly_trend": {
                "categories": months,
                "series": trend_scores
            },
            "recommendations": recommendations
        })

    except Exception as e:
        print("HR DASHBOARD DATA ERROR:", e)
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if conn:
            conn.close()


# ============================================================
# HR PROMOTION APPROVAL
# ============================================================

@dashboard_bp.route("/api/hr/approve-promotion", methods=["POST"])
def hr_approve_promotion():
    """
    Approve an employee's promotion: records in promotion_history and updates employee designation.
    """
    if "user_id" not in session:
        return jsonify({"success": False, "message": "Authentication required."}), 401

    role = _normalize_role(session.get("role_name", ""))
    if role not in {"hr", "admin"}:
        return jsonify({"success": False, "message": "HR or Admin access required."}), 403

    data = request.get_json(silent=True) or {}
    employee_id = data.get("employee_id")
    new_designation_id = data.get("new_designation_id")
    reason = data.get("reason", "Approved based on annual performance appraisal.")

    if not employee_id:
        return jsonify({"success": False, "message": "Employee ID is required."}), 400

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT designation_id, user_id FROM employees WHERE employee_id = %s", (employee_id,))
        emp_row = cursor.fetchone()
        if not emp_row:
            return jsonify({"success": False, "message": "Employee not found."}), 404

        old_desig_id = emp_row[0]
        emp_user_id = emp_row[1]

        # If new designation not provided, promote to next available designation
        if not new_designation_id:
            cursor.execute("SELECT designation_id FROM designations WHERE designation_id > %s ORDER BY designation_id ASC LIMIT 1", (old_desig_id or 0,))
            next_d = cursor.fetchone()
            target_desig_id = next_d[0] if next_d else old_desig_id
        else:
            target_desig_id = int(new_designation_id)

        # Record in promotion_history
        cursor.execute("""
            INSERT INTO promotion_history (employee_id, old_designation_id, new_designation_id, promotion_date, reason, created_at)
            VALUES (%s, %s, %s, CURRENT_DATE, %s, NOW())
        """, (employee_id, old_desig_id, target_desig_id, reason))

        # Update employee designation
        cursor.execute("UPDATE employees SET designation_id = %s WHERE employee_id = %s", (target_desig_id, employee_id))

        # Notify employee
        if emp_user_id:
            _safe_insert_notification(
                cursor,
                emp_user_id,
                "Promotion Approved!",
                "Congratulations! Your promotion has been approved by HR.",
                "appraisal"
            )

        conn.commit()
        return jsonify({"success": True, "message": "Promotion approved and recorded successfully."})

    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if conn:
            conn.close()


# ============================================================
# HR INCREMENT APPROVAL
# ============================================================

@dashboard_bp.route("/api/hr/approve-increment", methods=["POST"])
def hr_approve_increment():
    """
    Approve an employee's salary increment: records in increment_history.
    """
    if "user_id" not in session:
        return jsonify({"success": False, "message": "Authentication required."}), 401

    role = _normalize_role(session.get("role_name", ""))
    if role not in {"hr", "admin"}:
        return jsonify({"success": False, "message": "HR or Admin access required."}), 403

    data = request.get_json(silent=True) or {}
    employee_id = data.get("employee_id")
    increment_amount = data.get("increment_amount", 5000)
    reason = data.get("reason", "Approved based on annual performance appraisal.")

    if not employee_id:
        return jsonify({"success": False, "message": "Employee ID is required."}), 400

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT user_id FROM employees WHERE employee_id = %s", (employee_id,))
        emp_row = cursor.fetchone()
        if not emp_row:
            return jsonify({"success": False, "message": "Employee not found."}), 404

        emp_user_id = emp_row[0]

        # Record in increment_history
        cursor.execute("""
            INSERT INTO increment_history (employee_id, previous_salary, increment_amount, new_salary, increment_date, reason, created_at)
            VALUES (%s, 50000, %s, %s, CURRENT_DATE, %s, NOW())
        """, (employee_id, increment_amount, 50000 + float(increment_amount), reason))

        # Notify employee
        if emp_user_id:
            _safe_insert_notification(
                cursor,
                emp_user_id,
                "Salary Increment Approved!",
                "Congratulations! Your salary increment has been approved by HR.",
                "appraisal"
            )

        conn.commit()
        return jsonify({"success": True, "message": "Salary increment approved and recorded successfully."})

    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if conn:
            conn.close()


# ============================================================
# USER & EMPLOYEE CRUD MANAGEMENT API (HR & ADMIN)
# ============================================================

from werkzeug.security import generate_password_hash


@dashboard_bp.route("/api/admin/users", methods=["GET"])
def admin_list_users():
    """List all registered users with their roles and linked employee details."""
    if "user_id" not in session:
        return jsonify({"success": False, "message": "Authentication required."}), 401
    role = _normalize_role(session.get("role_name", ""))
    if role not in {"hr", "admin"}:
        return jsonify({"success": False, "message": "HR/Admin access required."}), 403

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT 
                u.user_id,
                u.username,
                u.role_id,
                r.role_name,
                u.created_at,
                e.employee_id,
                e.employee_code,
                CONCAT(e.first_name, ' ', e.last_name) AS employee_name,
                d.department_name,
                des.designation_name
            FROM users u
            JOIN roles r ON u.role_id = r.role_id
            LEFT JOIN employees e ON u.user_id = e.user_id
            LEFT JOIN departments d ON e.department_id = d.department_id
            LEFT JOIN designations des ON e.designation_id = des.designation_id
            ORDER BY u.user_id ASC
        """)
        rows = cur.fetchall()
        users = [
            {
                "user_id": r[0],
                "username": r[1],
                "role_id": r[2],
                "role_name": r[3],
                "created_at": r[4].strftime("%d-%b-%Y") if r[4] else None,
                "employee_id": r[5],
                "employee_code": r[6],
                "employee_name": r[7].strip() if r[7] else None,
                "department": r[8],
                "designation": r[9]
            }
            for r in rows
        ]
        return jsonify({"success": True, "users": users})
    finally:
        cur.close()
        conn.close()


@dashboard_bp.route("/api/admin/users", methods=["POST"])
def admin_create_user():
    """Create a new user account with hashed password."""
    if "user_id" not in session:
        return jsonify({"success": False, "message": "Authentication required."}), 401
    role = _normalize_role(session.get("role_name", ""))
    if role not in {"hr", "admin"}:
        return jsonify({"success": False, "message": "HR/Admin access required."}), 403

    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    role_id = data.get("role_id")

    if not username or not password or not role_id:
        return jsonify({"success": False, "message": "Username, password, and role_id are required."}), 400

    hashed_pw = generate_password_hash(password)
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT user_id FROM users WHERE LOWER(username) = LOWER(%s)", (username,))
        if cur.fetchone():
            return jsonify({"success": False, "message": "Username already exists."}), 409

        cur.execute("""
            INSERT INTO users (username, password, role_id, created_at)
            VALUES (%s, %s, %s, NOW())
            RETURNING user_id
        """, (username, hashed_pw, role_id))
        new_id = cur.fetchone()[0]
        conn.commit()
        return jsonify({"success": True, "message": "User created successfully.", "user_id": new_id}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        cur.close()
        conn.close()


@dashboard_bp.route("/api/admin/users/<int:user_id>", methods=["PUT"])
def admin_update_user(user_id):
    """Update user credentials or role."""
    if "user_id" not in session:
        return jsonify({"success": False, "message": "Authentication required."}), 401
    role = _normalize_role(session.get("role_name", ""))
    if role not in {"hr", "admin"}:
        return jsonify({"success": False, "message": "HR/Admin access required."}), 403

    data = request.get_json(silent=True) or {}
    username = data.get("username")
    role_id = data.get("role_id")
    password = data.get("password")

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT user_id FROM users WHERE user_id = %s", (user_id,))
        if not cur.fetchone():
            return jsonify({"success": False, "message": "User not found."}), 404

        if username:
            cur.execute("UPDATE users SET username = %s WHERE user_id = %s", (username.strip(), user_id))
        if role_id:
            cur.execute("UPDATE users SET role_id = %s WHERE user_id = %s", (role_id, user_id))
        if password and password.strip():
            cur.execute("UPDATE users SET password = %s WHERE user_id = %s", (generate_password_hash(password.strip()), user_id))

        conn.commit()
        return jsonify({"success": True, "message": "User updated successfully."})
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        cur.close()
        conn.close()


@dashboard_bp.route("/api/admin/users/<int:user_id>", methods=["DELETE"])
def admin_delete_user(user_id):
    """Delete a user account."""
    if "user_id" not in session:
        return jsonify({"success": False, "message": "Authentication required."}), 401
    role = _normalize_role(session.get("role_name", ""))
    if role not in {"hr", "admin"}:
        return jsonify({"success": False, "message": "HR/Admin access required."}), 403

    if session.get("user_id") == user_id:
        return jsonify({"success": False, "message": "Cannot delete currently logged-in account."}), 400

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE employees SET user_id = NULL WHERE user_id = %s", (user_id,))
        cur.execute("DELETE FROM users WHERE user_id = %s", (user_id,))
        conn.commit()
        return jsonify({"success": True, "message": "User deleted successfully."})
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        cur.close()
        conn.close()


@dashboard_bp.route("/api/admin/employees", methods=["GET"])
def admin_list_employees():
    """List all employees with details."""
    if "user_id" not in session:
        return jsonify({"success": False, "message": "Authentication required."}), 401
    role = _normalize_role(session.get("role_name", ""))
    if role not in {"hr", "admin"}:
        return jsonify({"success": False, "message": "HR/Admin access required."}), 403

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT 
                e.employee_id,
                e.employee_code,
                e.first_name,
                e.last_name,
                e.email,
                e.phone,
                e.department_id,
                d.department_name,
                e.designation_id,
                des.designation_name,
                e.manager_id,
                CONCAT(m.first_name, ' ', m.last_name) AS manager_name,
                e.employment_status,
                e.joining_date,
                e.user_id
            FROM employees e
            LEFT JOIN departments d ON e.department_id = d.department_id
            LEFT JOIN designations des ON e.designation_id = des.designation_id
            LEFT JOIN employees m ON e.manager_id = m.employee_id
            ORDER BY e.employee_id ASC
        """)
        rows = cur.fetchall()
        employees = [
            {
                "employee_id": r[0],
                "employee_code": r[1],
                "first_name": r[2],
                "last_name": r[3],
                "email": r[4],
                "phone": r[5],
                "department_id": r[6],
                "department_name": r[7],
                "designation_id": r[8],
                "designation_name": r[9],
                "manager_id": r[10],
                "manager_name": r[11].strip() if r[11] else None,
                "employment_status": r[12],
                "joining_date": r[13].strftime("%Y-%m-%d") if r[13] else None,
                "user_id": r[14]
            }
            for r in rows
        ]
        return jsonify({"success": True, "employees": employees})
    finally:
        cur.close()
        conn.close()


@dashboard_bp.route("/api/admin/employees", methods=["POST"])
def admin_create_employee():
    """Create a new employee profile."""
    if "user_id" not in session:
        return jsonify({"success": False, "message": "Authentication required."}), 401
    role = _normalize_role(session.get("role_name", ""))
    if role not in {"hr", "admin"}:
        return jsonify({"success": False, "message": "HR/Admin access required."}), 403

    data = request.get_json(silent=True) or {}
    employee_code = data.get("employee_code", "").strip()
    first_name = data.get("first_name", "").strip()
    last_name = data.get("last_name", "").strip()
    email = data.get("email", "").strip()
    phone = data.get("phone", "").strip()
    department_id = data.get("department_id")
    designation_id = data.get("designation_id")
    branch_id = data.get("branch_id", 1)
    manager_id = data.get("manager_id")
    joining_date = data.get("joining_date") or date.today()
    employment_status = data.get("employment_status", "Active")
    user_id = data.get("user_id")

    if not employee_code or not first_name or not last_name:
        return jsonify({"success": False, "message": "Employee Code, First Name, and Last Name are required."}), 400

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT employee_id FROM employees WHERE employee_code = %s", (employee_code,))
        if cur.fetchone():
            return jsonify({"success": False, "message": "Employee Code already exists."}), 409

        cur.execute("""
            INSERT INTO employees (
                employee_code, first_name, last_name, email, phone,
                department_id, designation_id, branch_id, manager_id,
                joining_date, employment_status, user_id, created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            RETURNING employee_id
        """, (
            employee_code, first_name, last_name, email, phone,
            department_id, designation_id, branch_id, manager_id,
            joining_date, employment_status, user_id
        ))
        emp_id = cur.fetchone()[0]
        conn.commit()
        return jsonify({"success": True, "message": "Employee created successfully.", "employee_id": emp_id}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        cur.close()
        conn.close()


@dashboard_bp.route("/api/admin/employees/<int:employee_id>", methods=["PUT"])
def admin_update_employee(employee_id):
    """Update existing employee details."""
    if "user_id" not in session:
        return jsonify({"success": False, "message": "Authentication required."}), 401
    role = _normalize_role(session.get("role_name", ""))
    if role not in {"hr", "admin"}:
        return jsonify({"success": False, "message": "HR/Admin access required."}), 403

    data = request.get_json(silent=True) or {}
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT employee_id FROM employees WHERE employee_id = %s", (employee_id,))
        if not cur.fetchone():
            return jsonify({"success": False, "message": "Employee not found."}), 404

        cur.execute("""
            UPDATE employees
            SET first_name = COALESCE(%s, first_name),
                last_name = COALESCE(%s, last_name),
                email = COALESCE(%s, email),
                phone = COALESCE(%s, phone),
                department_id = COALESCE(%s, department_id),
                designation_id = COALESCE(%s, designation_id),
                manager_id = COALESCE(%s, manager_id),
                employment_status = COALESCE(%s, employment_status)
            WHERE employee_id = %s
        """, (
            data.get("first_name"),
            data.get("last_name"),
            data.get("email"),
            data.get("phone"),
            data.get("department_id"),
            data.get("designation_id"),
            data.get("manager_id"),
            data.get("employment_status"),
            employee_id
        ))
        conn.commit()
        return jsonify({"success": True, "message": "Employee updated successfully."})
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        cur.close()
        conn.close()


@dashboard_bp.route("/api/admin/employees/<int:employee_id>", methods=["DELETE"])
def admin_delete_employee(employee_id):
    """Deactivate or delete employee record."""
    if "user_id" not in session:
        return jsonify({"success": False, "message": "Authentication required."}), 401
    role = _normalize_role(session.get("role_name", ""))
    if role not in {"hr", "admin"}:
        return jsonify({"success": False, "message": "HR/Admin access required."}), 403

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE employees SET employment_status = 'Inactive' WHERE employee_id = %s", (employee_id,))
        conn.commit()
        return jsonify({"success": True, "message": "Employee deactivated successfully."})
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        cur.close()
        conn.close()


@dashboard_bp.route("/api/admin/departments", methods=["GET"])
def admin_list_departments():
    """List departments."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT department_id, department_name, casual_leave_limit, sick_leave_limit, privileged_leave_limit FROM departments ORDER BY department_id ASC")
        rows = cur.fetchall()
        depts = [
            {
                "department_id": r[0],
                "department_name": r[1],
                "casual_leave_limit": r[2],
                "sick_leave_limit": r[3],
                "privileged_leave_limit": r[4]
            }
            for r in rows
        ]
        return jsonify({"success": True, "departments": depts})
    finally:
        cur.close()
        conn.close()


@dashboard_bp.route("/api/admin/departments", methods=["POST"])
def admin_create_department():
    """Create a new department."""
    if "user_id" not in session:
        return jsonify({"success": False, "message": "Authentication required."}), 401
    role = _normalize_role(session.get("role_name", ""))
    if role not in {"hr", "admin"}:
        return jsonify({"success": False, "message": "HR/Admin access required."}), 403

    data = request.get_json(silent=True) or {}
    name = data.get("department_name", "").strip()
    if not name:
        return jsonify({"success": False, "message": "Department name is required."}), 400

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO departments (department_name, casual_leave_limit, sick_leave_limit, privileged_leave_limit)
            VALUES (%s, %s, %s, %s)
            RETURNING department_id
        """, (
            name,
            data.get("casual_leave_limit", 12),
            data.get("sick_leave_limit", 10),
            data.get("privileged_leave_limit", 15)
        ))
        did = cur.fetchone()[0]
        conn.commit()
        return jsonify({"success": True, "message": "Department created successfully.", "department_id": did}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        cur.close()
        conn.close()


@dashboard_bp.route("/api/admin/designations", methods=["GET"])
def admin_list_designations():
    """List designations."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT designation_id, designation_name FROM designations ORDER BY designation_id ASC")
        rows = cur.fetchall()
        desigs = [{"designation_id": r[0], "designation_name": r[1]} for r in rows]
        return jsonify({"success": True, "designations": desigs})
    finally:
        cur.close()
        conn.close()


@dashboard_bp.route("/api/admin/designations", methods=["POST"])
def admin_create_designation():
    """Create a new designation."""
    if "user_id" not in session:
        return jsonify({"success": False, "message": "Authentication required."}), 401
    role = _normalize_role(session.get("role_name", ""))
    if role not in {"hr", "admin"}:
        return jsonify({"success": False, "message": "HR/Admin access required."}), 403

    data = request.get_json(silent=True) or {}
    name = data.get("designation_name", "").strip()
    if not name:
        return jsonify({"success": False, "message": "Designation name is required."}), 400

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO designations (designation_name) VALUES (%s) RETURNING designation_id", (name,))
        did = cur.fetchone()[0]
        conn.commit()
        return jsonify({"success": True, "message": "Designation created successfully.", "designation_id": did}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        cur.close()
        conn.close()


# ============================================================
# ORGANIZATION & HRMS ADMIN WEB ROUTES
# ============================================================

# --- DEPARTMENTS ---
@dashboard_bp.route("/admin/departments", methods=["GET", "POST"])
def admin_departments():
    if "user_id" not in session:
        return redirect(url_for("login_page"))
    role = _normalize_role(session.get("role_name", ""))
    if role not in {"hr", "admin"}:
        return "Access Denied. Administrator/HR access required.", 403

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        if request.method == "POST":
            name = (request.form.get("department_name") or "").strip()
            cl = request.form.get("casual_leave_limit", 12)
            sl = request.form.get("sick_leave_limit", 10)
            pl = request.form.get("privileged_leave_limit", 15)

            if not name:
                flash("Department name is required.", "danger")
            else:
                cur.execute("SELECT department_id FROM departments WHERE LOWER(department_name) = LOWER(%s)", (name,))
                if cur.fetchone():
                    flash("Department name already exists.", "danger")
                else:
                    cur.execute("""
                        INSERT INTO departments (department_name, casual_leave_limit, sick_leave_limit, privileged_leave_limit)
                        VALUES (%s, %s, %s, %s)
                    """, (name, cl, sl, pl))
                    conn.commit()
                    flash(f"Department '{name}' created successfully.", "success")
            return redirect("/admin/departments")

        cur.execute("""
            SELECT d.department_id, d.department_name, d.casual_leave_limit, d.sick_leave_limit, d.privileged_leave_limit,
                   COUNT(e.employee_id) AS employee_count
            FROM departments d
            LEFT JOIN employees e ON d.department_id = e.department_id
            GROUP BY d.department_id, d.department_name, d.casual_leave_limit, d.sick_leave_limit, d.privileged_leave_limit
            ORDER BY d.department_id ASC
        """)
        rows = cur.fetchall()
        depts = [
            {
                "department_id": r[0],
                "department_name": r[1],
                "casual_leave_limit": r[2],
                "sick_leave_limit": r[3],
                "privileged_leave_limit": r[4],
                "employee_count": r[5]
            }
            for r in rows
        ]
        return render_template("department_management.html", departments=depts)
    finally:
        cur.close()
        conn.close()


@dashboard_bp.route("/admin/departments/edit/<int:department_id>", methods=["POST"])
def admin_edit_department(department_id):
    if "user_id" not in session:
        return redirect(url_for("login_page"))
    role = _normalize_role(session.get("role_name", ""))
    if role not in {"hr", "admin"}:
        return "Access Denied. Administrator/HR access required.", 403

    name = (request.form.get("department_name") or "").strip()
    cl = request.form.get("casual_leave_limit", 12)
    sl = request.form.get("sick_leave_limit", 10)
    pl = request.form.get("privileged_leave_limit", 15)

    if not name:
        flash("Department name cannot be empty.", "danger")
        return redirect("/admin/departments")

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT department_id FROM departments WHERE LOWER(department_name) = LOWER(%s) AND department_id != %s", (name, department_id))
        if cur.fetchone():
            flash("Another department with this name already exists.", "danger")
            return redirect("/admin/departments")

        cur.execute("""
            UPDATE departments
            SET department_name = %s,
                casual_leave_limit = %s,
                sick_leave_limit = %s,
                privileged_leave_limit = %s
            WHERE department_id = %s
        """, (name, cl, sl, pl, department_id))
        conn.commit()
        flash("Department updated successfully.", "success")
        return redirect("/admin/departments")
    except Exception as e:
        conn.rollback()
        flash(f"Error updating department: {str(e)}", "danger")
        return redirect("/admin/departments")
    finally:
        cur.close()
        conn.close()


@dashboard_bp.route("/admin/departments/delete/<int:department_id>", methods=["POST"])
def admin_delete_department(department_id):
    if "user_id" not in session:
        return redirect(url_for("login_page"))
    role = _normalize_role(session.get("role_name", ""))
    if role not in {"hr", "admin"}:
        return "Access Denied. Administrator/HR access required.", 403

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM employees WHERE department_id = %s", (department_id,))
        count = cur.fetchone()[0]
        if count > 0:
            flash(f"Cannot delete department: {count} employee(s) are currently assigned to it.", "danger")
            return redirect("/admin/departments")

        cur.execute("DELETE FROM departments WHERE department_id = %s", (department_id,))
        conn.commit()
        flash("Department deleted successfully.", "success")
        return redirect("/admin/departments")
    except Exception as e:
        conn.rollback()
        flash(f"Error deleting department: {str(e)}", "danger")
        return redirect("/admin/departments")
    finally:
        cur.close()
        conn.close()


# --- BRANCHES ---
@dashboard_bp.route("/admin/branches", methods=["GET", "POST"])
def admin_branches():
    if "user_id" not in session:
        return redirect(url_for("login_page"))
    role = _normalize_role(session.get("role_name", ""))
    if role not in {"hr", "admin"}:
        return "Access Denied. Administrator/HR access required.", 403

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        if request.method == "POST":
            name = (request.form.get("branch_name") or "").strip()
            loc = (request.form.get("location") or "").strip()

            if not name:
                flash("Branch name is required.", "danger")
            else:
                cur.execute("SELECT branch_id FROM branches WHERE LOWER(branch_name) = LOWER(%s)", (name,))
                if cur.fetchone():
                    flash("Branch name already exists.", "danger")
                else:
                    cur.execute("INSERT INTO branches (branch_name, location) VALUES (%s, %s)", (name, loc or None))
                    conn.commit()
                    flash(f"Branch '{name}' created successfully.", "success")
            return redirect("/admin/branches")

        cur.execute("""
            SELECT b.branch_id, b.branch_name, b.location,
                   COUNT(e.employee_id) AS employee_count
            FROM branches b
            LEFT JOIN employees e ON b.branch_id = e.branch_id
            GROUP BY b.branch_id, b.branch_name, b.location
            ORDER BY b.branch_id ASC
        """)
        rows = cur.fetchall()
        branches = [
            {
                "branch_id": r[0],
                "branch_name": r[1],
                "location": r[2] or "",
                "employee_count": r[3]
            }
            for r in rows
        ]
        return render_template("branch_management.html", branches=branches)
    finally:
        cur.close()
        conn.close()


@dashboard_bp.route("/admin/branches/edit/<int:branch_id>", methods=["POST"])
def admin_edit_branch(branch_id):
    if "user_id" not in session:
        return redirect(url_for("login_page"))
    role = _normalize_role(session.get("role_name", ""))
    if role not in {"hr", "admin"}:
        return "Access Denied. Administrator/HR access required.", 403

    name = (request.form.get("branch_name") or "").strip()
    loc = (request.form.get("location") or "").strip()

    if not name:
        flash("Branch name cannot be empty.", "danger")
        return redirect("/admin/branches")

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT branch_id FROM branches WHERE LOWER(branch_name) = LOWER(%s) AND branch_id != %s", (name, branch_id))
        if cur.fetchone():
            flash("Another branch with this name already exists.", "danger")
            return redirect("/admin/branches")

        cur.execute("UPDATE branches SET branch_name = %s, location = %s WHERE branch_id = %s", (name, loc or None, branch_id))
        conn.commit()
        flash("Branch updated successfully.", "success")
        return redirect("/admin/branches")
    except Exception as e:
        conn.rollback()
        flash(f"Error updating branch: {str(e)}", "danger")
        return redirect("/admin/branches")
    finally:
        cur.close()
        conn.close()


@dashboard_bp.route("/admin/branches/delete/<int:branch_id>", methods=["POST"])
def admin_delete_branch(branch_id):
    if "user_id" not in session:
        return redirect(url_for("login_page"))
    role = _normalize_role(session.get("role_name", ""))
    if role not in {"hr", "admin"}:
        return "Access Denied. Administrator/HR access required.", 403

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM employees WHERE branch_id = %s", (branch_id,))
        count = cur.fetchone()[0]
        if count > 0:
            flash(f"Cannot delete branch: {count} employee(s) are currently assigned to it.", "danger")
            return redirect("/admin/branches")

        cur.execute("DELETE FROM branches WHERE branch_id = %s", (branch_id,))
        conn.commit()
        flash("Branch deleted successfully.", "success")
        return redirect("/admin/branches")
    except Exception as e:
        conn.rollback()
        flash(f"Error deleting branch: {str(e)}", "danger")
        return redirect("/admin/branches")
    finally:
        cur.close()
        conn.close()


# --- DESIGNATIONS ---
@dashboard_bp.route("/admin/designations", methods=["GET", "POST"])
def admin_designations():
    if "user_id" not in session:
        return redirect(url_for("login_page"))
    role = _normalize_role(session.get("role_name", ""))
    if role not in {"hr", "admin"}:
        return "Access Denied. Administrator/HR access required.", 403

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        if request.method == "POST":
            name = (request.form.get("designation_name") or "").strip()

            if not name:
                flash("Designation name is required.", "danger")
            else:
                cur.execute("SELECT designation_id FROM designations WHERE LOWER(designation_name) = LOWER(%s)", (name,))
                if cur.fetchone():
                    flash("Designation name already exists.", "danger")
                else:
                    cur.execute("INSERT INTO designations (designation_name) VALUES (%s)", (name,))
                    conn.commit()
                    flash(f"Designation '{name}' created successfully.", "success")
            return redirect("/admin/designations")

        cur.execute("""
            SELECT des.designation_id, des.designation_name,
                   COUNT(e.employee_id) AS employee_count
            FROM designations des
            LEFT JOIN employees e ON des.designation_id = e.designation_id
            GROUP BY des.designation_id, des.designation_name
            ORDER BY des.designation_id ASC
        """)
        rows = cur.fetchall()
        desigs = [
            {
                "designation_id": r[0],
                "designation_name": r[1],
                "employee_count": r[2]
            }
            for r in rows
        ]
        return render_template("designation_management.html", designations=desigs)
    finally:
        cur.close()
        conn.close()


@dashboard_bp.route("/admin/designations/edit/<int:designation_id>", methods=["POST"])
def admin_edit_designation(designation_id):
    if "user_id" not in session:
        return redirect(url_for("login_page"))
    role = _normalize_role(session.get("role_name", ""))
    if role not in {"hr", "admin"}:
        return "Access Denied. Administrator/HR access required.", 403

    name = (request.form.get("designation_name") or "").strip()
    if not name:
        flash("Designation name cannot be empty.", "danger")
        return redirect("/admin/designations")

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT designation_id FROM designations WHERE LOWER(designation_name) = LOWER(%s) AND designation_id != %s", (name, designation_id))
        if cur.fetchone():
            flash("Another designation with this name already exists.", "danger")
            return redirect("/admin/designations")

        cur.execute("UPDATE designations SET designation_name = %s WHERE designation_id = %s", (name, designation_id))
        conn.commit()
        flash("Designation updated successfully.", "success")
        return redirect("/admin/designations")
    except Exception as e:
        conn.rollback()
        flash(f"Error updating designation: {str(e)}", "danger")
        return redirect("/admin/designations")
    finally:
        cur.close()
        conn.close()


@dashboard_bp.route("/admin/designations/delete/<int:designation_id>", methods=["POST"])
def admin_delete_designation(designation_id):
    if "user_id" not in session:
        return redirect(url_for("login_page"))
    role = _normalize_role(session.get("role_name", ""))
    if role not in {"hr", "admin"}:
        return "Access Denied. Administrator/HR access required.", 403

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM employees WHERE designation_id = %s", (designation_id,))
        count = cur.fetchone()[0]
        if count > 0:
            flash(f"Cannot delete designation: {count} employee(s) are currently assigned to it.", "danger")
            return redirect("/admin/designations")

        cur.execute("DELETE FROM designations WHERE designation_id = %s", (designation_id,))
        conn.commit()
        flash("Designation deleted successfully.", "success")
        return redirect("/admin/designations")
    except Exception as e:
        conn.rollback()
        flash(f"Error deleting designation: {str(e)}", "danger")
        return redirect("/admin/designations")
    finally:
        cur.close()
        conn.close()


# --- USERS ---
@dashboard_bp.route("/admin/users", methods=["GET", "POST"])
def admin_users_page():
    if "user_id" not in session:
        return redirect(url_for("login_page"))
    role = _normalize_role(session.get("role_name", ""))
    if role not in {"hr", "admin"}:
        return "Access Denied. Administrator/HR access required.", 403

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        if request.method == "POST":
            username = (request.form.get("username") or "").strip()
            password = (request.form.get("password") or "").strip()
            role_id = request.form.get("role_id")
            employee_id = request.form.get("employee_id")

            if not username or not password or not role_id:
                flash("Username, password, and role are required.", "danger")
            else:
                cur.execute("SELECT user_id FROM users WHERE LOWER(username) = LOWER(%s)", (username,))
                if cur.fetchone():
                    flash("Username already exists.", "danger")
                else:
                    cur.execute("""
                        INSERT INTO users (username, password, role_id, created_at)
                        VALUES (%s, %s, %s, NOW())
                        RETURNING user_id
                    """, (username, generate_password_hash(password), int(role_id)))
                    new_uid = cur.fetchone()[0]

                    if employee_id and employee_id.strip():
                        cur.execute("UPDATE employees SET user_id = %s WHERE employee_id = %s", (new_uid, int(employee_id)))

                    conn.commit()
                    flash(f"User account '{username}' created successfully.", "success")
            return redirect("/admin/users")

        cur.execute("""
            SELECT u.user_id, u.username, u.role_id, r.role_name, u.created_at,
                   e.employee_id, e.employee_code, CONCAT(e.first_name, ' ', e.last_name) AS employee_name
            FROM users u
            JOIN roles r ON u.role_id = r.role_id
            LEFT JOIN employees e ON u.user_id = e.user_id
            ORDER BY u.user_id ASC
        """)
        user_rows = cur.fetchall()
        users = [
            {
                "user_id": r[0],
                "username": r[1],
                "role_id": r[2],
                "role_name": r[3],
                "created_at": r[4].strftime("%d-%b-%Y") if r[4] else None,
                "employee_id": r[5],
                "employee_code": r[6],
                "employee_name": r[7].strip() if r[7] else None
            }
            for r in user_rows
        ]

        cur.execute("SELECT role_id, role_name FROM roles ORDER BY role_id ASC")
        role_rows = cur.fetchall()
        roles = [{"role_id": r[0], "role_name": r[1]} for r in role_rows]

        cur.execute("SELECT employee_id, employee_code, first_name, last_name, user_id FROM employees ORDER BY first_name, last_name ASC")
        emp_rows = cur.fetchall()
        employees = [
            {
                "employee_id": r[0],
                "employee_code": r[1],
                "first_name": r[2],
                "last_name": r[3],
                "user_id": r[4]
            }
            for r in emp_rows
        ]
        user_employee_map = {e["user_id"]: e for e in employees if e["user_id"] is not None}

        return render_template(
            "user_management.html",
            users=users,
            roles=roles,
            employees=employees,
            user_employee_map=user_employee_map
        )
    finally:
        cur.close()
        conn.close()


@dashboard_bp.route("/admin/users/edit/<int:user_id>", methods=["POST"])
def admin_edit_user(user_id):
    if "user_id" not in session:
        return redirect(url_for("login_page"))
    role = _normalize_role(session.get("role_name", ""))
    if role not in {"hr", "admin"}:
        return "Access Denied. Administrator/HR access required.", 403

    username = (request.form.get("username") or "").strip()
    password = (request.form.get("password") or "").strip()
    role_id = request.form.get("role_id")
    employee_id = request.form.get("employee_id")

    if not username or not role_id:
        flash("Username and role are required.", "danger")
        return redirect("/admin/users")

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT user_id FROM users WHERE LOWER(username) = LOWER(%s) AND user_id != %s", (username, user_id))
        if cur.fetchone():
            flash("Another user with this username already exists.", "danger")
            return redirect("/admin/users")

        if password:
            cur.execute("""
                UPDATE users
                SET username = %s, role_id = %s, password = %s
                WHERE user_id = %s
            """, (username, int(role_id), generate_password_hash(password), user_id))
        else:
            cur.execute("""
                UPDATE users
                SET username = %s, role_id = %s
                WHERE user_id = %s
            """, (username, int(role_id), user_id))

        cur.execute("UPDATE employees SET user_id = NULL WHERE user_id = %s", (user_id,))
        if employee_id and employee_id.strip():
            cur.execute("UPDATE employees SET user_id = %s WHERE employee_id = %s", (user_id, int(employee_id)))

        conn.commit()
        flash("User account updated successfully.", "success")
        return redirect("/admin/users")
    except Exception as e:
        conn.rollback()
        flash(f"Error updating user account: {str(e)}", "danger")
        return redirect("/admin/users")
    finally:
        cur.close()
        conn.close()


@dashboard_bp.route("/admin/users/delete/<int:user_id>", methods=["POST"])
def admin_delete_user_web(user_id):
    if "user_id" not in session:
        return redirect(url_for("login_page"))
    role = _normalize_role(session.get("role_name", ""))
    if role not in {"hr", "admin"}:
        return "Access Denied. Administrator/HR access required.", 403

    if session.get("user_id") == user_id:
        flash("You cannot delete your own active administrator account.", "danger")
        return redirect("/admin/users")

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE employees SET user_id = NULL WHERE user_id = %s", (user_id,))
        cur.execute("DELETE FROM users WHERE user_id = %s", (user_id,))
        conn.commit()
        flash("User account deleted successfully.", "success")
        return redirect("/admin/users")
    except Exception as e:
        conn.rollback()
        flash(f"Error deleting user account: {str(e)}", "danger")
        return redirect("/admin/users")
    finally:
        cur.close()
        conn.close()


# --- EMPLOYEES DIRECTORY & ONBOARDING ---
@dashboard_bp.route("/admin/employees", methods=["GET"])
def admin_employees_page():
    if "user_id" not in session:
        return redirect(url_for("login_page"))
    role = _normalize_role(session.get("role_name", ""))
    if role not in {"hr", "admin"}:
        return "Access Denied. Administrator/HR access required.", 403

    search = request.args.get("search", "").strip()
    department_id = request.args.get("department_id", "").strip()
    branch_id = request.args.get("branch_id", "").strip()
    status = request.args.get("status", "").strip()

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        query = """
            SELECT 
                e.employee_id,
                e.employee_code,
                e.first_name,
                e.last_name,
                e.email,
                e.phone,
                e.department_id,
                d.department_name,
                e.designation_id,
                des.designation_name,
                e.branch_id,
                b.branch_name,
                e.manager_id,
                CONCAT(m.first_name, ' ', m.last_name) AS manager_name,
                e.employment_status,
                e.joining_date,
                e.user_id
            FROM employees e
            LEFT JOIN departments d ON e.department_id = d.department_id
            LEFT JOIN designations des ON e.designation_id = des.designation_id
            LEFT JOIN branches b ON e.branch_id = b.branch_id
            LEFT JOIN employees m ON e.manager_id = m.employee_id
            WHERE 1=1
        """
        params = []
        if search:
            query += " AND (e.employee_code ILIKE %s OR e.first_name ILIKE %s OR e.last_name ILIKE %s OR e.email ILIKE %s)"
            pattern = f"%{search}%"
            params.extend([pattern, pattern, pattern, pattern])
        if department_id:
            query += " AND e.department_id = %s"
            params.append(int(department_id))
        if branch_id:
            query += " AND e.branch_id = %s"
            params.append(int(branch_id))
        if status:
            query += " AND e.employment_status = %s"
            params.append(status)

        query += " ORDER BY e.employee_id ASC"
        cur.execute(query, tuple(params))
        rows = cur.fetchall()

        employees = [
            {
                "employee_id": r[0],
                "employee_code": r[1],
                "first_name": r[2],
                "last_name": r[3],
                "email": r[4],
                "phone": r[5],
                "department_id": r[6],
                "department_name": r[7],
                "designation_id": r[8],
                "designation_name": r[9],
                "branch_id": r[10],
                "branch_name": r[11],
                "manager_id": r[12],
                "manager_name": r[13].strip() if r[13] else None,
                "employment_status": r[14],
                "joining_date": r[15],
                "user_id": r[16]
            }
            for r in rows
        ]

        cur.execute("SELECT department_id, department_name FROM departments ORDER BY department_name ASC")
        dept_rows = cur.fetchall()
        departments = [{"department_id": r[0], "department_name": r[1]} for r in dept_rows]

        cur.execute("SELECT branch_id, branch_name FROM branches ORDER BY branch_name ASC")
        branch_rows = cur.fetchall()
        branches = [{"branch_id": r[0], "branch_name": r[1]} for r in branch_rows]

        cur.execute("SELECT COUNT(*) FROM employees")
        total_employees = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM employees WHERE employment_status = 'Active'")
        active_count = cur.fetchone()[0]

        return render_template(
            "employee_management.html",
            employees=employees,
            departments=departments,
            branches=branches,
            search=search,
            selected_department=department_id,
            selected_branch=branch_id,
            selected_status=status,
            total_employees=total_employees,
            active_count=active_count
        )
    finally:
        cur.close()
        conn.close()


@dashboard_bp.route("/admin/employees/add", methods=["GET", "POST"])
def admin_add_employee_page():
    if "user_id" not in session:
        return redirect(url_for("login_page"))
    role = _normalize_role(session.get("role_name", ""))
    if role not in {"hr", "admin"}:
        return "Access Denied. Administrator/HR access required.", 403

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT department_id, department_name FROM departments ORDER BY department_name ASC")
        departments = [{"department_id": r[0], "department_name": r[1]} for r in cur.fetchall()]

        cur.execute("SELECT branch_id, branch_name, location FROM branches ORDER BY branch_name ASC")
        branches = [{"branch_id": r[0], "branch_name": r[1], "location": r[2]} for r in cur.fetchall()]

        cur.execute("SELECT designation_id, designation_name FROM designations ORDER BY designation_name ASC")
        designations = [{"designation_id": r[0], "designation_name": r[1]} for r in cur.fetchall()]

        cur.execute("""
            SELECT DISTINCT e.employee_id, e.employee_code, e.first_name, e.last_name, des.designation_name
            FROM employees e
            LEFT JOIN designations des ON e.designation_id = des.designation_id
            LEFT JOIN users u ON e.user_id = u.user_id
            LEFT JOIN roles r ON u.role_id = r.role_id
            WHERE LOWER(COALESCE(r.role_name, '')) IN ('manager', 'team leader')
               OR LOWER(COALESCE(des.designation_name, '')) LIKE '%manager%'
               OR LOWER(COALESCE(des.designation_name, '')) LIKE '%leader%'
               OR e.employee_id IN (SELECT DISTINCT manager_id FROM employees WHERE manager_id IS NOT NULL)
            ORDER BY e.first_name, e.last_name ASC
        """)
        managers = [{"employee_id": r[0], "employee_code": r[1], "first_name": r[2], "last_name": r[3], "designation_name": r[4] or ""} for r in cur.fetchall()]

        if request.method == "POST":
            code = (request.form.get("employee_code") or "").strip()
            first_name = (request.form.get("first_name") or "").strip()
            last_name = (request.form.get("last_name") or "").strip()
            email = (request.form.get("email") or "").strip()
            phone = (request.form.get("phone") or "").strip()
            department_id = request.form.get("department_id") or None
            designation_id = request.form.get("designation_id") or None
            branch_id = request.form.get("branch_id") or None
            manager_id = request.form.get("manager_id") or None
            joining_date = request.form.get("joining_date") or None
            status = request.form.get("employment_status", "Active").strip()

            if not code or not first_name or not last_name:
                return render_template(
                    "add_employee.html",
                    departments=departments,
                    branches=branches,
                    designations=designations,
                    managers=managers,
                    error="Employee Code, First Name, and Last Name are required."
                )

            cur.execute("SELECT employee_id FROM employees WHERE LOWER(employee_code) = LOWER(%s)", (code,))
            if cur.fetchone():
                return render_template(
                    "add_employee.html",
                    departments=departments,
                    branches=branches,
                    designations=designations,
                    managers=managers,
                    error=f"Employee Code '{code}' already exists."
                )

            cur.execute("""
                INSERT INTO employees (
                    employee_code, first_name, last_name, email, phone,
                    department_id, designation_id, branch_id, manager_id,
                    joining_date, employment_status, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            """, (
                code, first_name, last_name,
                email or None, phone or None,
                int(department_id) if department_id else None,
                int(designation_id) if designation_id else None,
                int(branch_id) if branch_id else None,
                int(manager_id) if manager_id else None,
                joining_date if joining_date else None,
                status
            ))
            conn.commit()
            flash(f"Employee {first_name} {last_name} ({code}) added successfully.", "success")
            return redirect("/admin/employees")

        return render_template(
            "add_employee.html",
            departments=departments,
            branches=branches,
            designations=designations,
            managers=managers
        )
    finally:
        cur.close()
        conn.close()


@dashboard_bp.route("/admin/employees/edit/<int:employee_id>", methods=["GET", "POST"])
def admin_edit_employee_page(employee_id):
    if "user_id" not in session:
        return redirect(url_for("login_page"))
    role = _normalize_role(session.get("role_name", ""))
    if role not in {"hr", "admin"}:
        return "Access Denied. Administrator/HR access required.", 403

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT department_id, department_name FROM departments ORDER BY department_name ASC")
        departments = [{"department_id": r[0], "department_name": r[1]} for r in cur.fetchall()]

        cur.execute("SELECT branch_id, branch_name, location FROM branches ORDER BY branch_name ASC")
        branches = [{"branch_id": r[0], "branch_name": r[1], "location": r[2]} for r in cur.fetchall()]

        cur.execute("SELECT designation_id, designation_name FROM designations ORDER BY designation_name ASC")
        designations = [{"designation_id": r[0], "designation_name": r[1]} for r in cur.fetchall()]

        cur.execute("""
            SELECT DISTINCT e.employee_id, e.employee_code, e.first_name, e.last_name, des.designation_name
            FROM employees e
            LEFT JOIN designations des ON e.designation_id = des.designation_id
            LEFT JOIN users u ON e.user_id = u.user_id
            LEFT JOIN roles r ON u.role_id = r.role_id
            WHERE (LOWER(COALESCE(r.role_name, '')) IN ('manager', 'team leader')
               OR LOWER(COALESCE(des.designation_name, '')) LIKE '%%manager%%'
               OR LOWER(COALESCE(des.designation_name, '')) LIKE '%%leader%%'
               OR e.employee_id IN (SELECT DISTINCT manager_id FROM employees WHERE manager_id IS NOT NULL))
              AND e.employee_id != %s
            ORDER BY e.first_name, e.last_name ASC
        """, (employee_id,))
        managers = [{"employee_id": r[0], "employee_code": r[1], "first_name": r[2], "last_name": r[3], "designation_name": r[4] or ""} for r in cur.fetchall()]

        cur.execute("""
            SELECT employee_id, employee_code, first_name, last_name, email, phone,
                   department_id, designation_id, branch_id, manager_id,
                   joining_date, employment_status, user_id
            FROM employees WHERE employee_id = %s
        """, (employee_id,))
        emp_row = cur.fetchone()
        if not emp_row:
            flash("Employee not found.", "danger")
            return redirect("/admin/employees")

        employee = {
            "employee_id": emp_row[0],
            "employee_code": emp_row[1],
            "first_name": emp_row[2],
            "last_name": emp_row[3],
            "email": emp_row[4],
            "phone": emp_row[5],
            "department_id": emp_row[6],
            "designation_id": emp_row[7],
            "branch_id": emp_row[8],
            "manager_id": emp_row[9],
            "joining_date": emp_row[10],
            "employment_status": emp_row[11],
            "user_id": emp_row[12]
        }

        if request.method == "POST":
            code = (request.form.get("employee_code") or "").strip()
            first_name = (request.form.get("first_name") or "").strip()
            last_name = (request.form.get("last_name") or "").strip()
            email = (request.form.get("email") or "").strip()
            phone = (request.form.get("phone") or "").strip()
            department_id = request.form.get("department_id") or None
            designation_id = request.form.get("designation_id") or None
            branch_id = request.form.get("branch_id") or None
            manager_id = request.form.get("manager_id") or None
            joining_date = request.form.get("joining_date") or None
            status = request.form.get("employment_status", "Active").strip()

            if not code or not first_name or not last_name:
                return render_template(
                    "edit_employee.html",
                    employee=employee,
                    departments=departments,
                    branches=branches,
                    designations=designations,
                    managers=managers,
                    error="Employee Code, First Name, and Last Name are required."
                )

            cur.execute("SELECT employee_id FROM employees WHERE LOWER(employee_code) = LOWER(%s) AND employee_id != %s", (code, employee_id))
            if cur.fetchone():
                return render_template(
                    "edit_employee.html",
                    employee=employee,
                    departments=departments,
                    branches=branches,
                    designations=designations,
                    managers=managers,
                    error=f"Another employee with code '{code}' already exists."
                )

            cur.execute("""
                UPDATE employees
                SET employee_code = %s,
                    first_name = %s,
                    last_name = %s,
                    email = %s,
                    phone = %s,
                    department_id = %s,
                    designation_id = %s,
                    branch_id = %s,
                    manager_id = %s,
                    joining_date = %s,
                    employment_status = %s
                WHERE employee_id = %s
            """, (
                code, first_name, last_name,
                email or None, phone or None,
                int(department_id) if department_id else None,
                int(designation_id) if designation_id else None,
                int(branch_id) if branch_id else None,
                int(manager_id) if manager_id else None,
                joining_date if joining_date else None,
                status,
                employee_id
            ))
            conn.commit()
            flash(f"Employee {first_name} {last_name} ({code}) updated successfully.", "success")
            return redirect("/admin/employees")

        return render_template(
            "edit_employee.html",
            employee=employee,
            departments=departments,
            branches=branches,
            designations=designations,
            managers=managers
        )
    finally:
        cur.close()
        conn.close()


@dashboard_bp.route("/admin/employees/deactivate/<int:employee_id>", methods=["POST"])
def admin_toggle_employee_status(employee_id):
    if "user_id" not in session:
        return redirect(url_for("login_page"))
    role = _normalize_role(session.get("role_name", ""))
    if role not in {"hr", "admin"}:
        return "Access Denied. Administrator/HR access required.", 403

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT employment_status, first_name, last_name FROM employees WHERE employee_id = %s", (employee_id,))
        row = cur.fetchone()
        if not row:
            flash("Employee not found.", "danger")
            return redirect("/admin/employees")

        current_status, first_name, last_name = row
        new_status = "Inactive" if current_status == "Active" else "Active"
        cur.execute("UPDATE employees SET employment_status = %s WHERE employee_id = %s", (new_status, employee_id))
        conn.commit()
        flash(f"Status for {first_name} {last_name} changed to {new_status}.", "success")
        return redirect("/admin/employees")
    except Exception as e:
        conn.rollback()
        flash(f"Error toggling employee status: {str(e)}", "danger")
        return redirect("/admin/employees")
    finally:
        cur.close()
        conn.close()


@dashboard_bp.route("/admin/employees/profile/<int:employee_id>", methods=["GET"])
def admin_employee_profile_page(employee_id):
    if "user_id" not in session:
        return redirect(url_for("login_page"))
    role = _normalize_role(session.get("role_name", ""))
    if role not in {"hr", "admin"}:
        return "Access Denied. Administrator/HR access required.", 403

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT e.employee_id, e.employee_code, e.first_name, e.last_name, e.email, e.phone,
                   e.joining_date, e.employment_status, e.user_id,
                   d.department_id, d.department_name,
                   des.designation_id, des.designation_name,
                   b.branch_id, b.branch_name, b.location,
                   m.employee_id, m.employee_code, m.first_name, m.last_name
            FROM employees e
            LEFT JOIN departments d ON e.department_id = d.department_id
            LEFT JOIN designations des ON e.designation_id = des.designation_id
            LEFT JOIN branches b ON e.branch_id = b.branch_id
            LEFT JOIN employees m ON e.manager_id = m.employee_id
            WHERE e.employee_id = %s
        """, (employee_id,))
        r = cur.fetchone()
        if not r:
            flash("Employee not found.", "danger")
            return redirect("/admin/employees")

        employee = {
            "employee_id": r[0],
            "employee_code": r[1],
            "first_name": r[2],
            "last_name": r[3],
            "email": r[4],
            "phone": r[5],
            "joining_date": r[6],
            "employment_status": r[7],
            "user_id": r[8]
        }
        department = {"department_id": r[9], "department_name": r[10]} if r[9] else None
        designation = {"designation_id": r[11], "designation_name": r[12]} if r[11] else None
        branch = {"branch_id": r[13], "branch_name": r[14], "location": r[15]} if r[13] else None
        manager = {"employee_id": r[16], "employee_code": r[17], "first_name": r[18], "last_name": r[19]} if r[16] else None

        return render_template(
            "employee_profile.html",
            employee=employee,
            department=department,
            designation=designation,
            branch=branch,
            manager=manager
        )
    finally:
        cur.close()
        conn.close()


# --- HIERARCHY ---
@dashboard_bp.route("/admin/hierarchy", methods=["GET"])
def admin_hierarchy_page():
    if "user_id" not in session:
        return redirect(url_for("login_page"))
    role = _normalize_role(session.get("role_name", ""))
    if role not in {"hr", "admin"}:
        return "Access Denied. Administrator/HR access required.", 403

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT e.employee_id, e.employee_code, e.first_name, e.last_name, e.email,
                   e.department_id, d.department_name, e.manager_id
            FROM employees e
            LEFT JOIN departments d ON e.department_id = d.department_id
            ORDER BY e.employee_id ASC
        """)
        rows = cur.fetchall()
        employees = [
            {
                "employee_id": r[0],
                "employee_code": r[1],
                "first_name": r[2],
                "last_name": r[3],
                "email": r[4],
                "department_id": r[5],
                "department_name": r[6],
                "manager_id": r[7]
            }
            for r in rows
        ]

        cur.execute("""
            SELECT DISTINCT e.employee_id, e.employee_code, e.first_name, e.last_name, des.designation_name
            FROM employees e
            LEFT JOIN designations des ON e.designation_id = des.designation_id
            LEFT JOIN users u ON e.user_id = u.user_id
            LEFT JOIN roles r ON u.role_id = r.role_id
            WHERE LOWER(COALESCE(r.role_name, '')) IN ('manager', 'team leader')
               OR LOWER(COALESCE(des.designation_name, '')) LIKE '%manager%'
               OR LOWER(COALESCE(des.designation_name, '')) LIKE '%leader%'
               OR e.employee_id IN (SELECT DISTINCT manager_id FROM employees WHERE manager_id IS NOT NULL)
            ORDER BY e.first_name, e.last_name ASC
        """)
        mgr_rows = cur.fetchall()
        managers = [
            {
                "employee_id": r[0],
                "employee_code": r[1],
                "first_name": r[2],
                "last_name": r[3],
                "designation_name": r[4] or ""
            }
            for r in mgr_rows
        ]
        employee_map = {e["employee_id"]: e for e in employees}

        return render_template(
            "employee_hierarchy.html",
            employees=employees,
            managers=managers,
            employee_map=employee_map
        )
    finally:
        cur.close()
        conn.close()


@dashboard_bp.route("/admin/hierarchy/update/<int:employee_id>", methods=["POST"])
def admin_hierarchy_update(employee_id):
    if "user_id" not in session:
        return redirect(url_for("login_page"))
    role = _normalize_role(session.get("role_name", ""))
    if role not in {"hr", "admin"}:
        return "Access Denied. Administrator/HR access required.", 403

    manager_id = (request.form.get("manager_id") or "").strip()
    mgr_val = int(manager_id) if manager_id else None

    if mgr_val == employee_id:
        flash("An employee cannot be designated as their own reporting manager.", "danger")
        return redirect("/admin/hierarchy")

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE employees SET manager_id = %s WHERE employee_id = %s", (mgr_val, employee_id))
        conn.commit()
        flash("Reporting manager assignment updated successfully.", "success")
        return redirect("/admin/hierarchy")
    except Exception as e:
        conn.rollback()
        flash(f"Error updating hierarchy: {str(e)}", "danger")
        return redirect("/admin/hierarchy")
    finally:
        cur.close()
        conn.close()


# --- MANAGER APPRAISAL ---
@dashboard_bp.route("/manager/appraisal", methods=["GET", "POST"])
def manager_appraisal_page():
    if "user_id" not in session:
        return redirect(url_for("login_page"))
    role = _normalize_role(session.get("role_name", ""))
    if role not in {"manager", "admin"}:
        return "Access Denied. Manager access required.", 403

    if request.method == "POST":
        emp_id = request.form.get("employee_id")
        mgr_id = request.form.get("manager_id") or session.get("employee_id")
        cycle_name = request.form.get("cycle_name", "Annual 2026")

        try:
            prod = float(request.form.get("productivity", 0) or 0)
            qual = float(request.form.get("quality", 0) or 0)
            team = float(request.form.get("teamwork", 0) or 0)
            comm = float(request.form.get("communication", 0) or 0)
            prob = float(request.form.get("problem_solving", 0) or 0)
            init = float(request.form.get("initiative", 0) or 0)
            comp = float(request.form.get("compliance", 0) or 0)
            comments = request.form.get("manager_comments", "")
            total = prod + qual + team + comm + prob + init + comp

            conn = get_db_connection()
            cur = conn.cursor()
            try:
                cur.execute("SELECT cycle_id FROM appraisal_cycles WHERE status = 'Active' LIMIT 1")
                cycle_row = cur.fetchone()
                cycle_id = cycle_row[0] if cycle_row else 1

                cur.execute("""
                    INSERT INTO manager_appraisal (
                        employee_id, manager_id, cycle_id, productivity, quality_of_work,
                        teamwork, communication, problem_solving, initiative, compliance,
                        total_score, manager_comments, status, appraisal_date, created_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'Submitted', CURRENT_DATE, NOW())
                """, (
                    int(emp_id), int(mgr_id) if mgr_id else None, cycle_id,
                    prod, qual, team, comm, prob, init, comp,
                    total, comments
                ))

                # Notify employee
                cur.execute("SELECT user_id, first_name, last_name FROM employees WHERE employee_id = %s", (int(emp_id),))
                emp_info = cur.fetchone()
                if emp_info and emp_info[0]:
                    _safe_insert_notification(
                        cur,
                        emp_info[0],
                        "Manager Appraisal Submitted",
                        "Your manager has submitted your annual appraisal evaluation.",
                        "appraisal"
                    )

                # Notify HR admins
                cur.execute("""
                    INSERT INTO notifications (user_id, title, message, notification_type, is_read, created_at)
                    SELECT u.user_id, 'Appraisal Evaluation Completed', %s, 'appraisal', FALSE, NOW()
                    FROM users u
                    JOIN roles r ON u.role_id = r.role_id
                    WHERE LOWER(r.role_name) IN ('hr', 'admin', 'human resources')
                      AND NOT EXISTS (
                          SELECT 1 FROM notifications n
                          WHERE n.user_id = u.user_id
                            AND n.title = 'Appraisal Evaluation Completed'
                            AND n.message = %s
                            AND n.is_read = FALSE
                      )
                """, (f"Manager appraisal submitted for employee #{emp_id}.", f"Manager appraisal submitted for employee #{emp_id}."))

                conn.commit()
                flash("Manager appraisal evaluation submitted successfully.", "success")
            finally:
                cur.close()
                conn.close()
        except Exception as e:
            flash(f"Error submitting appraisal: {str(e)}", "danger")

        return redirect("/manager/appraisal")

    return render_template("manager_appraisal.html")


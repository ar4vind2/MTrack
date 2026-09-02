from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from config import get_db_connection


# ============================================================
# BLUEPRINT
# ============================================================

kra_kpi_bp = Blueprint("kra_kpi", __name__)


@kra_kpi_bp.before_request
def require_kra_kpi_administrator():
    """Restrict KRA/KPI master data and assignments to HR administrators."""
    if "user_id" not in session:
        return redirect(url_for("login_page"))

    if session.get("role_name", "").lower() not in {"hr", "admin"}:
        return "Access Denied", 403


# ============================================================
# KRA MANAGEMENT
# ============================================================

@kra_kpi_bp.route("/kra-management")
@kra_kpi_bp.route("/kra_management.html")
def kra_management():

    conn = None
    cursor = None

    try:

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                kra_id,
                kra_name,
                description,
                default_weightage,
                created_at
            FROM kra_master
            ORDER BY kra_id DESC
        """)

        kras = cursor.fetchall()

        return render_template(
            "kra_management.html",
            kras=kras
        )

    except Exception as e:

        return f"Error loading KRA Management page: {str(e)}", 500

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()


# ============================================================
# ADD KRA
# ============================================================

@kra_kpi_bp.route("/add-kra", methods=["POST"])
def add_kra():

    conn = None
    cursor = None

    try:

        kra_name = request.form.get("kra_name")
        description = request.form.get("description")
        default_weightage = request.form.get("default_weightage")

        if not kra_name:
            return "KRA Name is required.", 400

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO kra_master
            (
                kra_name,
                description,
                default_weightage
            )
            VALUES (%s, %s, %s)
        """, (
            kra_name,
            description,
            default_weightage
        ))

        conn.commit()

        flash("KRA added successfully.", "success")

        return redirect(
            url_for("kra_kpi.kra_management")
        )

    except Exception as e:

        if conn:
            conn.rollback()

        return f"Error adding KRA: {str(e)}", 500

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()


# ============================================================
# EDIT KRA
# ============================================================

@kra_kpi_bp.route("/edit-kra/<int:kra_id>", methods=["POST"])
def edit_kra(kra_id):

    conn = None
    cursor = None

    try:

        kra_name = request.form.get("kra_name")
        description = request.form.get("description")
        default_weightage = request.form.get("default_weightage")

        if not kra_name:
            return "KRA Name is required.", 400

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE kra_master
            SET
                kra_name = %s,
                description = %s,
                default_weightage = %s
            WHERE kra_id = %s
        """, (
            kra_name,
            description,
            default_weightage,
            kra_id
        ))

        conn.commit()

        flash("KRA updated successfully.", "success")

        return redirect(
            url_for("kra_kpi.kra_management")
        )

    except Exception as e:

        if conn:
            conn.rollback()

        return f"Error updating KRA: {str(e)}", 500

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()


# ============================================================
# DELETE KRA
# ============================================================

@kra_kpi_bp.route("/delete-kra/<int:kra_id>", methods=["POST"])
def delete_kra(kra_id):

    conn = None
    cursor = None

    try:

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            DELETE FROM kra_master
            WHERE kra_id = %s
        """, (kra_id,))

        conn.commit()

        flash("KRA deleted successfully.", "success")

        return redirect(
            url_for("kra_kpi.kra_management")
        )

    except Exception as e:

        if conn:
            conn.rollback()

        return f"Error deleting KRA: {str(e)}", 500

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()


# ============================================================
# ASSIGN KRA PAGE
# ============================================================

@kra_kpi_bp.route("/assign-kra")
@kra_kpi_bp.route("/assign_kra.html")
def assign_kra():

    conn = None
    cursor = None

    try:

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                employee_id,
                first_name,
                last_name,
                employee_code
            FROM employees
            WHERE employment_status IS NULL
               OR employment_status = 'Active'
            ORDER BY first_name, last_name
        """)

        employees = cursor.fetchall()

        cursor.execute("""
            SELECT
                kra_id,
                kra_name,
                default_weightage
            FROM kra_master
            ORDER BY kra_name
        """)

        kras = cursor.fetchall()

        cursor.execute("""
            SELECT
                ek.employee_kra_id,
                e.first_name,
                e.last_name,
                e.employee_code,
                km.kra_name,
                ek.assigned_weightage,
                ek.target_value,
                ek.due_date,
                ek.status

            FROM employee_kra ek

            INNER JOIN employees e
                ON ek.employee_id = e.employee_id

            INNER JOIN kra_master km
                ON ek.kra_id = km.kra_id

            ORDER BY ek.employee_kra_id DESC
        """)

        assignments = cursor.fetchall()

        return render_template(
            "assign_kra.html",
            employees=employees,
            kras=kras,
            assignments=assignments
        )

    except Exception as e:

        return f"Error loading Assign KRA page: {str(e)}", 500

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()


# ============================================================
# SAVE ASSIGNED KRA
# ============================================================

@kra_kpi_bp.route("/assign-kra", methods=["POST"])
def save_assign_kra():

    conn = None
    cursor = None

    try:

        employee_id = request.form.get("employee_id")
        kra_id = request.form.get("kra_id")
        assigned_weightage = request.form.get("assigned_weightage")
        target_value = request.form.get("target_value")
        due_date = request.form.get("due_date")

        if not employee_id:
            return "Please select an employee.", 400

        if not kra_id:
            return "Please select a KRA.", 400

        if not assigned_weightage:
            return "Assigned weightage is required.", 400

        if not due_date:
            return "Due date is required.", 400

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO employee_kra
            (
                employee_id,
                kra_id,
                assigned_weightage,
                target_value,
                due_date,
                status
            )
            VALUES
            (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s
            )
        """, (
            employee_id,
            kra_id,
            assigned_weightage,
            target_value,
            due_date,
            "Active"
        ))

        conn.commit()

        flash("KRA assigned successfully!", "success")

        return redirect(
            url_for("kra_kpi.assign_kra")
        )

    except Exception as e:

        if conn:
            conn.rollback()

        return f"Error assigning KRA: {str(e)}", 500

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()


# ============================================================
# DELETE KRA ASSIGNMENT
# ============================================================

@kra_kpi_bp.route(
    "/delete-kra-assignment/<int:employee_kra_id>",
    methods=["POST"]
)
def delete_kra_assignment(employee_kra_id):

    conn = None
    cursor = None

    try:

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            DELETE FROM employee_kra
            WHERE employee_kra_id = %s
        """, (employee_kra_id,))

        conn.commit()

        return redirect(
            url_for("kra_kpi.assign_kra")
        )

    except Exception as e:

        if conn:
            conn.rollback()

        return f"Error deleting KRA assignment: {str(e)}", 500

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()


# ============================================================
# KPI MANAGEMENT
# ============================================================

@kra_kpi_bp.route("/kpi-management")
@kra_kpi_bp.route("/kpi_management.html")
def kpi_management():

    conn = None
    cursor = None

    try:

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                kpi_id,
                kpi_name,
                description,
                unit
            FROM kpi_master
            ORDER BY kpi_id DESC
        """)

        kpis = cursor.fetchall()

        return render_template(
            "kpi_management.html",
            kpis=kpis
        )

    except Exception as e:

        return f"Error loading KPI Management page: {str(e)}", 500

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()


# ============================================================
# ADD KPI
# ============================================================

@kra_kpi_bp.route("/add-kpi", methods=["POST"])
def add_kpi():

    conn = None
    cursor = None

    try:

        kpi_name = request.form.get("kpi_name")
        description = request.form.get("description")
        unit = request.form.get("unit")

        if not kpi_name:
            return "KPI Name is required.", 400

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO kpi_master
            (
                kpi_name,
                description,
                unit
            )
            VALUES (%s, %s, %s)
        """, (
            kpi_name,
            description,
            unit
        ))

        conn.commit()

        return redirect(
            url_for("kra_kpi.kpi_management")
        )

    except Exception as e:

        if conn:
            conn.rollback()

        return f"Error adding KPI: {str(e)}", 500

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()


# ============================================================
# EDIT KPI
# ============================================================

@kra_kpi_bp.route("/edit-kpi/<int:kpi_id>", methods=["POST"])
def edit_kpi(kpi_id):

    conn = None
    cursor = None

    try:

        kpi_name = request.form.get("kpi_name")
        description = request.form.get("description")
        unit = request.form.get("unit")

        if not kpi_name:
            return "KPI Name is required.", 400

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE kpi_master
            SET
                kpi_name = %s,
                description = %s,
                unit = %s
            WHERE kpi_id = %s
        """, (
            kpi_name,
            description,
            unit,
            kpi_id
        ))

        conn.commit()

        return redirect(
            url_for("kra_kpi.kpi_management")
        )

    except Exception as e:

        if conn:
            conn.rollback()

        return f"Error updating KPI: {str(e)}", 500

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()


# ============================================================
# DELETE KPI
# ============================================================

@kra_kpi_bp.route("/delete-kpi/<int:kpi_id>", methods=["POST"])
def delete_kpi(kpi_id):

    conn = None
    cursor = None

    try:

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            DELETE FROM kpi_master
            WHERE kpi_id = %s
        """, (kpi_id,))

        conn.commit()

        return redirect(
            url_for("kra_kpi.kpi_management")
        )

    except Exception as e:

        if conn:
            conn.rollback()

        return f"Error deleting KPI: {str(e)}", 500

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()


# ============================================================
# ASSIGN KPI PAGE
# ============================================================

@kra_kpi_bp.route("/assign-kpi")
@kra_kpi_bp.route("/assign_kpi.html")
def assign_kpi():

    conn = None
    cursor = None

    try:

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                employee_id,
                first_name,
                last_name,
                employee_code
            FROM employees
            WHERE employment_status IS NULL
               OR employment_status = 'Active'
            ORDER BY first_name, last_name
        """)

        employees = cursor.fetchall()

        cursor.execute("""
            SELECT
                kpi_id,
                kpi_name,
                unit
            FROM kpi_master
            ORDER BY kpi_name
        """)

        kpis = cursor.fetchall()

        cursor.execute("""
            SELECT
                ek.employee_kpi_id,
                e.first_name,
                e.last_name,
                e.employee_code,
                km.kpi_name,
                ek.assigned_target,
                ek.appraisal_period,
                ek.start_date,
                ek.end_date,
                ek.status
            FROM employee_kpi ek

            INNER JOIN employees e
                ON ek.employee_id = e.employee_id

            INNER JOIN kpi_master km
                ON ek.kpi_id = km.kpi_id

            ORDER BY ek.employee_kpi_id DESC
        """)

        assignments = cursor.fetchall()

        return render_template(
            "assign_kpi.html",
            employees=employees,
            kpis=kpis,
            assignments=assignments
        )

    except Exception as e:

        return f"Error loading Assign KPI page: {str(e)}", 500

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()

# ============================================================
# SAVE ASSIGNED KPI
# ============================================================

@kra_kpi_bp.route("/assign-kpi", methods=["POST"])
def save_assign_kpi():

    conn = None
    cursor = None

    try:

        # ----------------------------------------------------
        # Get form values
        # ----------------------------------------------------

        employee_id = request.form.get("employee_id")
        kpi_id = request.form.get("kpi_id")
        assigned_target = request.form.get("assigned_target")
        appraisal_period = request.form.get("appraisal_period")
        start_date = request.form.get("start_date")
        end_date = request.form.get("end_date")


        # ----------------------------------------------------
        # Validate required fields
        # ----------------------------------------------------

        if not employee_id:
            return "Please select an employee.", 400

        if not kpi_id:
            return "Please select a KPI.", 400

        if not assigned_target:
            return "Target value is required.", 400

        if not appraisal_period:
            return "Appraisal period is required.", 400

        if not start_date:
            return "Start date is required.", 400

        if not end_date:
            return "End date is required.", 400


        # ----------------------------------------------------
        # Database connection
        # ----------------------------------------------------

        conn = get_db_connection()
        cursor = conn.cursor()


        # ----------------------------------------------------
        # Verify employee
        # ----------------------------------------------------

        cursor.execute("""
            SELECT employee_id
            FROM employees
            WHERE employee_id = %s
        """, (employee_id,))

        if not cursor.fetchone():

            return "Selected employee does not exist.", 400


        # ----------------------------------------------------
        # Verify KPI
        # ----------------------------------------------------

        cursor.execute("""
            SELECT kpi_id
            FROM kpi_master
            WHERE kpi_id = %s
        """, (kpi_id,))

        if not cursor.fetchone():

            return "Selected KPI does not exist.", 400


        # ----------------------------------------------------
        # Get logged-in user
        # ----------------------------------------------------

        assigned_by = session.get("user_id")


        # ----------------------------------------------------
        # Insert KPI assignment
        # ----------------------------------------------------

        cursor.execute("""
            INSERT INTO employee_kpi
            (
                employee_id,
                kpi_id,
                assigned_target,
                appraisal_period,
                start_date,
                end_date,
                status,
                assigned_by,
                assigned_at
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
                CURRENT_TIMESTAMP
            )
        """, (
            employee_id,
            kpi_id,
            assigned_target,
            appraisal_period,
            start_date,
            end_date,
            "Active",
            assigned_by
        ))


        # ----------------------------------------------------
        # Save
        # ----------------------------------------------------

        conn.commit()

        flash("KPI assigned successfully!", "success")

        return redirect(url_for("kra_kpi.assign_kpi"))


    except Exception as e:

        if conn:
            conn.rollback()

        print(
            "Error assigning KPI:",
            e
        )

        return (
            f"Error assigning KPI: {str(e)}",
            500
        )


    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()

# ============================================================
# DELETE KPI ASSIGNMENT
# ============================================================

@kra_kpi_bp.route(
    "/delete-kpi-assignment/<int:employee_kpi_id>",
    methods=["POST"]
)
def delete_kpi_assignment(employee_kpi_id):

    conn = None
    cursor = None

    try:

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            DELETE FROM employee_kpi
            WHERE employee_kpi_id = %s
        """, (employee_kpi_id,))

        conn.commit()

        return redirect(
            url_for("kra_kpi.assign_kpi")
        )

    except Exception as e:

        if conn:
            conn.rollback()

        return f"Error deleting KPI assignment: {str(e)}", 500

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()


# ============================================================
# KPI RECORDS PAGE
# ============================================================

@kra_kpi_bp.route("/kpi-records")
@kra_kpi_bp.route("/kpi_records.html")
def kpi_records():

    conn = None
    cursor = None

    try:

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                kr.employee_kpi_id,

                e.employee_code,
                e.first_name,
                e.last_name,

                km.kpi_name,

                kr.achieved_value,
                kr.evaluation_month,
                kr.remarks

            FROM kpi_records kr

            INNER JOIN employees e
                ON kr.employee_id = e.employee_id

            INNER JOIN kpi_master km
                ON kr.kpi_id = km.kpi_id

            ORDER BY
                kr.evaluation_month DESC,
                kr.employee_kpi_id DESC
        """)

        records = cursor.fetchall()

        cursor.execute("""
            SELECT
                employee_id,
                first_name,
                last_name,
                employee_code
            FROM employees
            WHERE employment_status IS NULL
               OR employment_status = 'Active'
            ORDER BY first_name, last_name
        """)

        employees = cursor.fetchall()

        cursor.execute("""
            SELECT
                kpi_id,
                kpi_name,
                unit
            FROM kpi_master
            ORDER BY kpi_name
        """)

        kpis = cursor.fetchall()

        return render_template(
            "kpi_records.html",
            records=records,
            employees=employees,
            kpis=kpis
        )

    except Exception as e:

        return f"Error loading KPI Records page: {str(e)}", 500

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()


# ============================================================
# ADD KPI RECORD
# ============================================================

@kra_kpi_bp.route("/add-kpi-record", methods=["POST"])
def add_kpi_record():

    conn = None
    cursor = None

    try:

        employee_id = request.form.get("employee_id")
        kpi_id = request.form.get("kpi_id")
        achieved_value = request.form.get("achieved_value")
        evaluation_month = request.form.get("evaluation_month")

        if evaluation_month:
            evaluation_month = evaluation_month + "-01"
        remarks = request.form.get("remarks")

        if not employee_id:
            return "Please select an employee.", 400

        if not kpi_id:
            return "Please select a KPI.", 400

        if not achieved_value:
            return "Achieved value is required.", 400

        if not evaluation_month:
            return "Evaluation month is required.", 400

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO kpi_records
            (
                employee_id,
                kpi_id,
                achieved_value,
                evaluation_month,
                remarks
            )
            VALUES
            (
                %s,
                %s,
                %s,
                %s,
                %s
            )
        """, (
            employee_id,
            kpi_id,
            achieved_value,
            evaluation_month,
            remarks
        ))

        conn.commit()

        flash("KPI record added successfully!", "success")

        return redirect(
            url_for("kra_kpi.kpi_records")
        )

    except Exception as e:

        if conn:
            conn.rollback()

        return f"Error adding KPI record: {str(e)}", 500

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()


# ============================================================
# DELETE KPI RECORD
# ============================================================

@kra_kpi_bp.route(
    "/delete-kpi-record/<int:employee_kpi_id>",
    methods=["POST"]
)
def delete_kpi_record(employee_kpi_id):

    conn = None
    cursor = None

    try:

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            DELETE FROM kpi_records
            WHERE employee_kpi_id = %s
        """, (employee_kpi_id,))

        conn.commit()

        return redirect(
            url_for("kra_kpi.kpi_records")
        )

    except Exception as e:

        if conn:
            conn.rollback()

        return f"Error deleting KPI record: {str(e)}", 500

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()

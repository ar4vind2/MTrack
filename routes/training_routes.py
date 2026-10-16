import os
from datetime import datetime, date, time
from flask import Blueprint, jsonify, request, send_from_directory, current_app
from werkzeug.utils import secure_filename
from config import get_db_connection

training_bp = Blueprint("training", __name__, url_prefix="/api")

UPLOAD_FOLDER = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "static",
    "certificates"
)


# ---------------------------------------------------------
# STATUS CALCULATION HELPERS (DATE & TIME BASED)
# ---------------------------------------------------------
def parse_date_val(d):
    if d is None:
        return None
    if isinstance(d, datetime):
        return d.date()
    if isinstance(d, date):
        return d
    if isinstance(d, str):
        try:
            return datetime.strptime(d.strip()[:10], "%Y-%m-%d").date()
        except Exception:
            return None
    return None


def parse_time_val(t):
    if t is None:
        return None
    if isinstance(t, time):
        return t
    if isinstance(t, str):
        t_str = t.strip()
        for fmt in ("%H:%M:%S", "%H:%M"):
            try:
                return datetime.strptime(t_str, fmt).time()
            except ValueError:
                pass
    return None


def compute_session_status(session_date, start_time=None, end_time=None, now=None):
    """
    Computes session status based on date and time.
    Returns: 'Pending', 'In Progress', or 'Completed'
    """
    if now is None:
        now = datetime.now()
    cur_date = now.date()
    cur_time = now.time()

    s_date = parse_date_val(session_date)
    if not s_date:
        return "Pending"

    s_start_time = parse_time_val(start_time)
    s_end_time = parse_time_val(end_time)

    if cur_date < s_date:
        return "Pending"
    elif cur_date > s_date:
        return "Completed"
    else:  # cur_date == s_date
        if s_start_time and cur_time < s_start_time:
            return "Pending"
        if s_end_time and cur_time > s_end_time:
            return "Completed"
        return "In Progress"


def compute_training_status(start_date, end_date, sessions=None, now=None):
    """
    Computes training program status dynamically based on start date,
    end date, and session dates/times.
    Returns: 'Pending', 'In Progress', or 'Completed'
    """
    if now is None:
        now = datetime.now()

    p_start_date = parse_date_val(start_date)
    p_end_date = parse_date_val(end_date)

    session_start_dt = None
    session_end_dt = None

    if sessions:
        valid_start_dts = []
        valid_end_dts = []
        for s in sessions:
            s_d = parse_date_val(s.get("session_date") if isinstance(s, dict) else getattr(s, "session_date", None))
            if not s_d:
                continue
            s_st = parse_time_val(s.get("start_time") if isinstance(s, dict) else getattr(s, "start_time", None)) or time.min
            s_et = parse_time_val(s.get("end_time") if isinstance(s, dict) else getattr(s, "end_time", None)) or time.max
            valid_start_dts.append(datetime.combine(s_d, s_st))
            valid_end_dts.append(datetime.combine(s_d, s_et))

        if valid_start_dts:
            session_start_dt = min(valid_start_dts)
        if valid_end_dts:
            session_end_dt = max(valid_end_dts)

    # Determine effective start datetime
    if p_start_date:
        start_time_candidates = [
            parse_time_val(s.get("start_time") if isinstance(s, dict) else getattr(s, "start_time", None))
            for s in (sessions or [])
            if parse_date_val(s.get("session_date") if isinstance(s, dict) else getattr(s, "session_date", None)) == p_start_date
        ]
        start_time_candidates = [t for t in start_time_candidates if t is not None]
        eff_start_time = min(start_time_candidates) if start_time_candidates else time.min
        prog_start_dt = datetime.combine(p_start_date, eff_start_time)
    else:
        prog_start_dt = None

    if prog_start_dt and session_start_dt:
        earliest_start = min(prog_start_dt, session_start_dt)
    elif prog_start_dt:
        earliest_start = prog_start_dt
    else:
        earliest_start = session_start_dt

    # Determine effective end datetime
    if p_end_date:
        end_time_candidates = [
            parse_time_val(s.get("end_time") if isinstance(s, dict) else getattr(s, "end_time", None))
            for s in (sessions or [])
            if parse_date_val(s.get("session_date") if isinstance(s, dict) else getattr(s, "session_date", None)) == p_end_date
        ]
        end_time_candidates = [t for t in end_time_candidates if t is not None]
        eff_end_time = max(end_time_candidates) if end_time_candidates else time.max
        prog_end_dt = datetime.combine(p_end_date, eff_end_time)
    else:
        prog_end_dt = None

    if prog_end_dt and session_end_dt:
        latest_end = max(prog_end_dt, session_end_dt)
    elif prog_end_dt:
        latest_end = prog_end_dt
    else:
        latest_end = session_end_dt

    if not earliest_start and not latest_end:
        return "Pending"

    if earliest_start and now < earliest_start:
        return "Pending"

    if latest_end and now > latest_end:
        return "Completed"

    return "In Progress"


def compute_employee_training_status(start_date, end_date, sessions=None, certificate=False, now=None):
    """
    Computes individual employee training assignment status based on date, time, and certification.
    """
    if now is None:
        now = datetime.now()

    base_status = compute_training_status(start_date, end_date, sessions, now=now)

    # If certificate has been uploaded/issued and the training has already started
    if certificate and base_status != "Pending":
        return "Completed"

    return base_status


def sync_training_statuses(cur):
    """
    Synchronizes status column in training_records based on date, time, sessions, and certification.
    """
    now = datetime.now()
    cur.execute("""
        SELECT 
            tp.program_id,
            tp.start_date,
            tp.end_date,
            ts.session_id,
            ts.session_date,
            ts.start_time,
            ts.end_time
        FROM training_programs tp
        LEFT JOIN training_sessions ts ON tp.program_id = ts.program_id
    """)
    rows = cur.fetchall()

    prog_data = {}
    for r in rows:
        pid = r[0]
        if pid not in prog_data:
            prog_data[pid] = {
                "start_date": r[1],
                "end_date": r[2],
                "sessions": []
            }
        if r[3] is not None:
            prog_data[pid]["sessions"].append({
                "session_id": r[3],
                "session_date": r[4],
                "start_time": r[5],
                "end_time": r[6]
            })

    for pid, data in prog_data.items():
        base_status = compute_training_status(
            data["start_date"],
            data["end_date"],
            data["sessions"],
            now=now
        )
        cur.execute("""
            UPDATE training_records
            SET status = CASE
                WHEN certificate = TRUE AND %s != 'Pending' THEN 'Completed'
                ELSE %s
            END
            WHERE program_id = %s
        """, (base_status, base_status, pid))



# ---------------------------------------------------------
# GET ALL EMPLOYEES (FOR SELECTION)
# ---------------------------------------------------------
@training_bp.route("/employees", methods=["GET"])
def get_employees():
    search = request.args.get("search", "").strip()

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        if search:
            cur.execute(
                """
                SELECT
                    e.employee_id,
                    e.employee_code,
                    e.first_name,
                    e.last_name,
                    e.email,
                    d.department_name
                FROM employees e
                LEFT JOIN departments d
                    ON e.department_id = d.department_id
                WHERE LOWER(COALESCE(e.first_name, '') || ' ' || COALESCE(e.last_name, '')) LIKE LOWER(%s)
                   OR LOWER(COALESCE(e.employee_code, '')) LIKE LOWER(%s)
                ORDER BY e.first_name, e.last_name
                """,
                (f"%{search}%", f"%{search}%")
            )
        else:
            cur.execute(
                """
                SELECT
                    e.employee_id,
                    e.employee_code,
                    e.first_name,
                    e.last_name,
                    e.email,
                    d.department_name
                FROM employees e
                LEFT JOIN departments d
                    ON e.department_id = d.department_id
                ORDER BY e.first_name, e.last_name
                """
            )

        rows = cur.fetchall()

        employees = [
            {
                "employee_id": row[0],
                "employee_code": row[1] or "",
                "name": f"{row[2] or ''} {row[3] or ''}".strip(),
                "email": row[4] or "",
                "department": row[5] or ""
            }
            for row in rows
        ]

        return jsonify(employees), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()


# ---------------------------------------------------------
# GET ALL DEPARTMENTS
# ---------------------------------------------------------
@training_bp.route("/departments", methods=["GET"])
def get_departments():
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT department_id, department_name
            FROM departments
            ORDER BY department_name
            """
        )

        rows = cur.fetchall()

        departments = [
            {
                "department_id": row[0],
                "department_name": row[1]
            }
            for row in rows
        ]

        return jsonify(departments), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()


# ---------------------------------------------------------
# GET ALL TRAINING PROGRAMS
# ---------------------------------------------------------
@training_bp.route("/training", methods=["GET"])
def get_training_records():
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        sync_training_statuses(cur)
        conn.commit()

        # Fetch all training sessions to map session times to programs
        cur.execute("""
            SELECT program_id, session_id, session_date, start_time, end_time
            FROM training_sessions
            ORDER BY session_date, start_time
        """)
        session_rows = cur.fetchall()
        prog_sessions = {}
        for s in session_rows:
            prog_sessions.setdefault(s[0], []).append({
                "session_id": s[1],
                "session_date": s[2],
                "start_time": s[3],
                "end_time": s[4]
            })

        cur.execute(
            """
            SELECT
                tp.program_id,
                tp.training_name,
                tp.training_type,
                tp.trainer_name,
                tp.start_date,
                tp.end_date,
                tp.remarks,
                tp.created_at,
                COUNT(tr.training_id) AS employee_count,
                AVG(tr.score) AS score,
                BOOL_OR(COALESCE(tr.certificate, FALSE)) AS certificate
            FROM training_programs tp
            LEFT JOIN training_records tr
                ON tp.program_id = tr.program_id
            GROUP BY
                tp.program_id,
                tp.training_name,
                tp.training_type,
                tp.trainer_name,
                tp.start_date,
                tp.end_date,
                tp.remarks,
                tp.created_at
            ORDER BY tp.created_at DESC
            """
        )

        rows = cur.fetchall()
        now = datetime.now()

        records = [
            {
                "training_id": row[0],
                "program_id": row[0],
                "training_code": "TR" + str(row[0]).zfill(3),
                "training_name": row[1],
                "training_type": row[2],
                "trainer_name": row[3],
                "start_date": row[4].isoformat() if row[4] else None,
                "end_date": row[5].isoformat() if row[5] else None,
                "remarks": row[6] or "",
                "created_at": row[7].isoformat() if row[7] else None,
                "employee_count": row[8],
                "status": compute_training_status(row[4], row[5], prog_sessions.get(row[0], []), now=now),
                "score": float(row[9]) if row[9] is not None else None,
                "certificate": bool(row[10]) if row[10] is not None else False
            }
            for row in rows
        ]

        return jsonify(records), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()


# ---------------------------------------------------------
# GET SINGLE TRAINING PROGRAM DETAILS
# ---------------------------------------------------------
@training_bp.route("/training/<int:program_id>", methods=["GET"])
def get_training_details(program_id):
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT
                tp.program_id,
                tp.training_name,
                tp.training_type,
                tp.trainer_name,
                tp.start_date,
                tp.end_date,
                tp.remarks
            FROM training_programs tp
            WHERE tp.program_id = %s
            """,
            (program_id,)
        )

        row = cur.fetchone()

        if not row:
            return jsonify({"error": "Training program not found"}), 404

        cur.execute(
            """
            SELECT session_id, session_date, start_time, end_time, session_name
            FROM training_sessions
            WHERE program_id = %s
            ORDER BY session_date, start_time
            """,
            (program_id,)
        )
        s_rows = cur.fetchall()
        now = datetime.now()
        sessions = [
            {
                "session_id": s[0],
                "session_date": s[1].isoformat() if s[1] else None,
                "session_date_formatted": s[1].strftime("%d %b %Y") if hasattr(s[1], "strftime") else (str(s[1]) if s[1] else None),
                "start_time": s[2].strftime("%H:%M") if hasattr(s[2], "strftime") else (str(s[2])[:5] if s[2] else None),
                "end_time": s[3].strftime("%H:%M") if hasattr(s[3], "strftime") else (str(s[3])[:5] if s[3] else None),
                "session_name": s[4] if len(s) > 4 and s[4] else f"Session {s[0]}",
                "status": compute_session_status(s[1], s[2], s[3], now=now)
            }
            for s in s_rows
        ]

        prog_status = compute_training_status(row[4], row[5], sessions, now=now)

        training = {
            "training_id": row[0],
            "program_id": row[0],
            "training_code": "TR" + str(row[0]).zfill(3),
            "training_name": row[1],
            "training_type": row[2],
            "trainer_name": row[3],
            "start_date": row[4].isoformat() if row[4] else None,
            "end_date": row[5].isoformat() if row[5] else None,
            "remarks": row[6] or "",
            "status": prog_status,
            "sessions": sessions
        }

        return jsonify(training), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()


# ---------------------------------------------------------
# CREATE A TRAINING PROGRAM WITH ASSIGNED EMPLOYEES
# ---------------------------------------------------------
@training_bp.route("/training", methods=["POST"])
def add_training():
    data = request.get_json() or {}

    employee_ids = data.get("employee_ids", [])
    training_name = data.get("training_name")
    training_type = data.get("training_type")
    trainer_name = data.get("trainer_name")
    start_date = data.get("start_date") or None
    end_date = data.get("end_date") or None
    remarks = data.get("remarks", "")

    if not employee_ids:
        return jsonify({"error": "Please select at least one employee"}), 400

    if not training_name or not training_type or not trainer_name:
        return jsonify({"error": "Required fields are missing"}), 400

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Create training program
        cur.execute(
            """
            INSERT INTO training_programs
            (
                training_name,
                training_type,
                trainer_name,
                start_date,
                end_date,
                remarks
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING program_id
            """,
            (
                training_name,
                training_type,
                trainer_name,
                start_date,
                end_date,
                remarks
            )
        )

        program_id = cur.fetchone()[0]

        # Calculate initial status based on date/time
        initial_status = compute_training_status(start_date, end_date, now=datetime.now())

        # Assign each employee
        training_ids = []
        for employee_id in employee_ids:
            cur.execute(
                """
                INSERT INTO training_records
                (
                    employee_id,
                    training_name,
                    training_type,
                    trainer_name,
                    start_date,
                    end_date,
                    status,
                    remarks,
                    program_id
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING training_id
                """,
                (
                    employee_id,
                    training_name,
                    training_type,
                    trainer_name,
                    start_date,
                    end_date,
                    initial_status,
                    remarks,
                    program_id
                )
            )
            training_ids.append(cur.fetchone()[0])

        conn.commit()

        return jsonify({
            "message": "Training program created successfully",
            "program_id": program_id,
            "training_ids": training_ids
        }), 201

    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()


# ---------------------------------------------------------
# GET EMPLOYEES ASSIGNED TO A TRAINING PROGRAM
# ---------------------------------------------------------
@training_bp.route("/training/<int:program_id>/employees", methods=["GET"])
def get_training_employees(program_id):
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("SELECT start_date, end_date FROM training_programs WHERE program_id = %s", (program_id,))
        p_row = cur.fetchone()
        p_start = p_row[0] if p_row else None
        p_end = p_row[1] if p_row else None

        cur.execute("SELECT session_id, session_date, start_time, end_time FROM training_sessions WHERE program_id = %s", (program_id,))
        sess_rows = cur.fetchall()
        sessions = [{"session_id": s[0], "session_date": s[1], "start_time": s[2], "end_time": s[3]} for s in sess_rows]

        cur.execute(
            """
            SELECT
                tr.employee_id,
                e.employee_code,
                e.first_name,
                e.last_name,
                d.department_name,
                tr.status,
                tr.score,
                tr.certificate,
                tr.certificate_file
            FROM training_records tr
            JOIN employees e
                ON tr.employee_id = e.employee_id
            LEFT JOIN departments d
                ON e.department_id = d.department_id
            WHERE tr.program_id = %s
            ORDER BY e.first_name, e.last_name
            """,
            (program_id,)
        )

        rows = cur.fetchall()
        now = datetime.now()

        employees = [
            {
                "employee_id": row[0],
                "employee_code": row[1] or "",
                "employee_name": f"{row[2] or ''} {row[3] or ''}".strip(),
                "department": row[4] or "—",
                "status": compute_employee_training_status(p_start, p_end, sessions, certificate=bool(row[7]), now=now),
                "score": float(row[6]) if row[6] is not None else None,
                "certificate": bool(row[7]),
                "certificate_file": row[8]
            }
            for row in rows
        ]

        return jsonify(employees), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()


# ---------------------------------------------------------
# UPLOAD CERTIFICATE
# ---------------------------------------------------------
@training_bp.route(
    "/training/<int:program_id>/employees/<int:employee_id>/certificate",
    methods=["POST"]
)
@training_bp.route(
    "/api/training/<int:program_id>/employees/<int:employee_id>/certificate",
    methods=["POST"]
)
def upload_training_certificate(program_id, employee_id):
    if "certificate" not in request.files:
        return jsonify({"error": "No certificate file selected"}), 400

    file = request.files["certificate"]
    if file.filename == "":
        return jsonify({"error": "No certificate file selected"}), 400

    allowed_extensions = {".pdf", ".jpg", ".jpeg", ".png"}
    extension = os.path.splitext(file.filename)[1].lower()

    if extension not in allowed_extensions:
        return jsonify({
            "error": "Only PDF, JPG, JPEG and PNG files are allowed"
        }), 400

    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT training_id
            FROM training_records
            WHERE program_id = %s
              AND employee_id = %s
            LIMIT 1
            """,
            (program_id, employee_id)
        )

        record = cur.fetchone()
        if not record:
            return jsonify({
                "error": "Employee is not assigned to this training"
            }), 404

        training_id = record[0]

        filename = secure_filename(
            f"training_{program_id}_employee_{employee_id}{extension}"
        )
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(file_path)

        certificate_path = f"certificates/{filename}"

        cur.execute(
            """
            UPDATE training_records
            SET certificate = TRUE,
                certificate_file = %s,
                status = CASE
                    WHEN CURRENT_DATE >= start_date THEN 'Completed'
                    ELSE status
                END
            WHERE training_id = %s
            """,
            (certificate_path, training_id)
        )

        conn.commit()

        return jsonify({
            "message": "Certificate uploaded successfully",
            "certificate_file": certificate_path
        }), 200

    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()


# ---------------------------------------------------------
# VIEW / DOWNLOAD CERTIFICATE
# ---------------------------------------------------------
@training_bp.route(
    "/training/<int:program_id>/employees/<int:employee_id>/certificate",
    methods=["GET"]
)
@training_bp.route(
    "/api/training/<int:program_id>/employees/<int:employee_id>/certificate",
    methods=["GET"]
)
def view_training_certificate(program_id, employee_id):
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT certificate_file
            FROM training_records
            WHERE program_id = %s
              AND employee_id = %s
            LIMIT 1
            """,
            (program_id, employee_id)
        )

        row = cur.fetchone()

        if not row or not row[0]:
            return jsonify({"error": "Certificate not found"}), 404

        certificate_path = row[0]
        filename = os.path.basename(certificate_path)
        file_path = os.path.join(UPLOAD_FOLDER, filename)

        if not os.path.exists(file_path):
            return jsonify({"error": "Certificate file not found on disk"}), 404

        return send_from_directory(UPLOAD_FOLDER, filename)

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()


# ---------------------------------------------------------
# DELETE CERTIFICATE
# ---------------------------------------------------------
@training_bp.route(
    "/training/<int:program_id>/employees/<int:employee_id>/certificate",
    methods=["DELETE"]
)
def delete_training_certificate(program_id, employee_id):
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT certificate_file
            FROM training_records
            WHERE program_id = %s
              AND employee_id = %s
            LIMIT 1
            """,
            (program_id, employee_id)
        )

        row = cur.fetchone()
        if not row:
            return jsonify({"error": "Training assignment not found"}), 404

        certificate_file = row[0]
        if not certificate_file:
            return jsonify({"error": "Certificate not found"}), 404

        filename = os.path.basename(certificate_file)
        file_path = os.path.join(UPLOAD_FOLDER, filename)

        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass

        cur.execute(
            """
            UPDATE training_records
            SET certificate = FALSE,
                certificate_file = NULL,
                status = CASE
                    WHEN CURRENT_DATE < start_date THEN 'Pending'
                    WHEN CURRENT_DATE > end_date THEN 'Completed'
                    ELSE 'In Progress'
                END
            WHERE program_id = %s
              AND employee_id = %s
            """,
            (program_id, employee_id)
        )

        conn.commit()

        return jsonify({"message": "Certificate deleted successfully"}), 200

    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()


# ---------------------------------------------------------
# GET EMPLOYEE TRAINING HISTORY
# ---------------------------------------------------------
@training_bp.route(
    "/training/employee/<int:employee_id>/history",
    methods=["GET"]
)
def get_employee_training_history(employee_id):
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT
                tr.training_id,
                tr.program_id,
                tr.training_name,
                tr.training_type,
                tr.trainer_name,
                tr.start_date,
                tr.end_date,
                tr.status,
                tr.score,
                tr.certificate,
                tr.certificate_file
            FROM training_records tr
            WHERE tr.employee_id = %s
            ORDER BY tr.start_date DESC NULLS LAST,
                     tr.training_id DESC
            """,
            (employee_id,)
        )

        # Fetch sessions for all programs in this employee's records
        cur.execute(
            """
            SELECT ts.program_id, ts.session_id, ts.session_date, ts.start_time, ts.end_time
            FROM training_sessions ts
            JOIN training_records tr ON ts.program_id = tr.program_id
            WHERE tr.employee_id = %s
            ORDER BY ts.session_date, ts.start_time
            """,
            (employee_id,)
        )
        s_rows = cur.fetchall()
        prog_sessions = {}
        for s in s_rows:
            prog_sessions.setdefault(s[0], []).append({
                "session_id": s[1],
                "session_date": s[2],
                "start_time": s[3],
                "end_time": s[4]
            })

        rows = cur.fetchall()
        now = datetime.now()

        history = [
            {
                "training_id": row[0],
                "program_id": row[1],
                "training_code": "TR" + str(row[1]).zfill(3),
                "training_name": row[2],
                "training_type": row[3],
                "trainer_name": row[4],
                "start_date": row[5].isoformat() if row[5] else None,
                "end_date": row[6].isoformat() if row[6] else None,
                "status": compute_employee_training_status(row[5], row[6], prog_sessions.get(row[1], []), certificate=bool(row[9]), now=now),
                "score": float(row[8]) if row[8] is not None else None,
                "certificate": bool(row[9]),
                "certificate_file": row[10]
            }
            for row in rows
        ]

        return jsonify(history), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()


# ---------------------------------------------------------
# ADD TRAINING SESSION
# ---------------------------------------------------------
@training_bp.route("/training/<int:program_id>/sessions", methods=["POST"])
def add_training_session(program_id):
    data = request.get_json() or {}

    session_date = data.get("session_date")
    session_name = data.get("session_name")
    start_time = data.get("start_time") or None
    end_time = data.get("end_time") or None

    if not session_date:
        return jsonify({"error": "Session date is required"}), 400

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT program_id
            FROM training_programs
            WHERE program_id = %s
            """,
            (program_id,)
        )

        if not cur.fetchone():
            return jsonify({"error": "Training program not found"}), 404

        cur.execute(
            """
            INSERT INTO training_sessions
            (
                program_id,
                session_date,
                session_name,
                start_time,
                end_time
            )
            VALUES (%s, %s, %s, %s, %s)
            RETURNING session_id
            """,
            (
                program_id,
                session_date,
                session_name,
                start_time,
                end_time
            )
        )

        session_id = cur.fetchone()[0]
        conn.commit()

        return jsonify({
            "message": "Training session added successfully",
            "session_id": session_id
        }), 201

    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()


# ---------------------------------------------------------
# GET SESSIONS FOR A TRAINING PROGRAM
# ---------------------------------------------------------
@training_bp.route(
    "/training/<int:program_id>/sessions",
    methods=["GET"]
)
def get_training_sessions(program_id):
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT
                session_id,
                session_date,
                session_name,
                start_time,
                end_time
            FROM training_sessions
            WHERE program_id = %s
            ORDER BY session_date, session_id
            """,
            (program_id,)
        )

        rows = cur.fetchall()
        now = datetime.now()

        sessions = [
            {
                "session_id": row[0],
                "session_date": row[1].isoformat() if row[1] else None,
                "session_name": row[2] or "",
                "start_time": row[3].strftime("%H:%M") if row[3] else None,
                "end_time": row[4].strftime("%H:%M") if row[4] else None,
                "status": compute_session_status(row[1], row[3], row[4], now=now)
            }
            for row in rows
        ]

        return jsonify(sessions), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()


# ---------------------------------------------------------
# GET SESSIONS AND ATTENDANCE FOR AN EMPLOYEE IN A PROGRAM
# ---------------------------------------------------------
@training_bp.route(
    "/training/<int:program_id>/employees/<int:employee_id>/sessions",
    methods=["GET"]
)
@training_bp.route(
    "/training/<int:program_id>/employee/<int:employee_id>/sessions",
    methods=["GET"]
)
def get_employee_program_sessions(program_id, employee_id):
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT
                ts.session_id,
                ts.session_date,
                ts.session_name,
                ts.start_time,
                ts.end_time,
                COALESCE(ta.attendance_status, 'Not Marked') AS attendance_status
            FROM training_sessions ts
            JOIN training_records tr
                ON ts.program_id = tr.program_id
               AND tr.employee_id = %s
            LEFT JOIN training_attendance ta
                ON ta.session_id = ts.session_id
               AND ta.employee_id = tr.employee_id
            WHERE ts.program_id = %s
            ORDER BY ts.session_date, ts.start_time, ts.session_id
            """,
            (employee_id, program_id)
        )

        rows = cur.fetchall()
        now = datetime.now()

        sessions = [
            {
                "session_id": row[0],
                "session_date": row[1].isoformat() if row[1] else None,
                "session_date_formatted": row[1].strftime("%d %b %Y") if hasattr(row[1], "strftime") else (str(row[1]) if row[1] else None),
                "session_name": row[2] or f"Session {row[0]}",
                "start_time": row[3].strftime("%H:%M") if hasattr(row[3], "strftime") else (str(row[3])[:5] if row[3] else None),
                "end_time": row[4].strftime("%H:%M") if hasattr(row[4], "strftime") else (str(row[4])[:5] if row[4] else None),
                "attendance_status": row[5],
                "status": compute_session_status(row[1], row[3], row[4], now=now)
            }
            for row in rows
        ]

        return jsonify(sessions), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()


# ---------------------------------------------------------
# MARK ATTENDANCE FOR A TRAINING SESSION
# ---------------------------------------------------------
@training_bp.route(
    "/training/<int:program_id>/sessions/<int:session_id>/attendance",
    methods=["POST"]
)
def mark_training_attendance(program_id, session_id):
    data = request.get_json() or {}

    employee_id = data.get("employee_id")
    attendance_status = data.get("attendance_status")

    allowed_statuses = {
        "Attended",
        "Absent",
        "Approved Leave",
        "Not Marked"
    }

    if not employee_id or attendance_status not in allowed_statuses:
        return jsonify({
            "error": "Valid employee and attendance status are required"
        }), 400

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT session_id
            FROM training_sessions
            WHERE session_id = %s
              AND program_id = %s
            """,
            (session_id, program_id)
        )

        if not cur.fetchone():
            return jsonify({"error": "Training session not found"}), 404

        cur.execute(
            """
            SELECT training_id
            FROM training_records
            WHERE program_id = %s
              AND employee_id = %s
            """,
            (program_id, employee_id)
        )

        if not cur.fetchone():
            return jsonify({
                "error": "Employee is not assigned to this training"
            }), 404

        if attendance_status == "Not Marked":
            cur.execute(
                """
                DELETE FROM training_attendance
                WHERE session_id = %s
                  AND employee_id = %s
                """,
                (session_id, employee_id)
            )
        else:
            cur.execute(
                """
                INSERT INTO training_attendance
                (
                    session_id,
                    employee_id,
                    attendance_status
                )
                VALUES (%s, %s, %s)
                ON CONFLICT (session_id, employee_id)
                DO UPDATE SET
                    attendance_status = EXCLUDED.attendance_status,
                    marked_at = CURRENT_TIMESTAMP
                """,
                (session_id, employee_id, attendance_status)
            )

        # Calculate session-wise attendance score for this program
        cur.execute(
            """
            SELECT
                COUNT(*) FILTER (WHERE ta.attendance_status = 'Attended') AS attended,
                COUNT(*) FILTER (WHERE ta.attendance_status = 'Absent') AS absent,
                COUNT(*) FILTER (WHERE ta.attendance_status = 'Approved Leave') AS approved_leave,
                COUNT(ts.session_id) AS total_sessions
            FROM training_sessions ts
            JOIN training_records tr
                ON tr.program_id = ts.program_id
               AND tr.employee_id = %s
            LEFT JOIN training_attendance ta
                ON ta.session_id = ts.session_id
               AND ta.employee_id = %s
            WHERE ts.program_id = %s
            """,
            (employee_id, employee_id, program_id)
        )
        prog_row = cur.fetchone()
        prog_attended = prog_row[0] or 0
        prog_absent = prog_row[1] or 0
        prog_approved_leave = prog_row[2] or 0
        prog_total_sessions = prog_row[3] or 0

        prog_expected = prog_attended + prog_absent
        if prog_expected > 0:
            program_attendance_score = round((prog_attended / prog_expected) * 100.0, 2)
        else:
            program_attendance_score = None

        # Determine training record status dynamically based on date/time and certification
        cur.execute("SELECT start_date, end_date FROM training_programs WHERE program_id = %s", (program_id,))
        prog_info = cur.fetchone()
        p_start = prog_info[0] if prog_info else None
        p_end = prog_info[1] if prog_info else None

        cur.execute("SELECT session_id, session_date, start_time, end_time FROM training_sessions WHERE program_id = %s", (program_id,))
        s_rows = cur.fetchall()
        p_sessions = [{"session_id": s[0], "session_date": s[1], "start_time": s[2], "end_time": s[3]} for s in s_rows]

        cur.execute("SELECT certificate FROM training_records WHERE program_id = %s AND employee_id = %s", (program_id, employee_id))
        cert_row = cur.fetchone()
        has_cert = bool(cert_row[0]) if cert_row else False

        prog_status = compute_employee_training_status(p_start, p_end, p_sessions, certificate=has_cert, now=datetime.now())

        cur.execute(
            """
            UPDATE training_records
            SET score = %s,
                status = %s
            WHERE program_id = %s
              AND employee_id = %s
            """,
            (program_attendance_score, prog_status, program_id, employee_id)
        )

        # Synchronize employee's overall session-wise training attendance score in performance_result
        cur.execute(
            """
            SELECT
                COUNT(DISTINCT tr.program_id) AS assigned_programs,
                COUNT(*) FILTER (WHERE ta.attendance_status = 'Attended') AS attended,
                COUNT(*) FILTER (WHERE ta.attendance_status = 'Absent') AS absent
            FROM training_records tr
            LEFT JOIN training_sessions ts
                ON ts.program_id = tr.program_id
            LEFT JOIN training_attendance ta
                ON ta.session_id = ts.session_id
               AND ta.employee_id = tr.employee_id
            WHERE tr.employee_id = %s
            """,
            (employee_id,)
        )
        tot_row = cur.fetchone()
        if tot_row and (tot_row[0] or 0) > 0 and ((tot_row[1] or 0) + (tot_row[2] or 0)) > 0:
            overall_training_score = round(((tot_row[1] or 0) / ((tot_row[1] or 0) + (tot_row[2] or 0))) * 100.0, 2)
        else:
            overall_training_score = None

        cur.execute(
            """
            UPDATE performance_result
            SET training_score = %s
            WHERE employee_id = %s
            """,
            (overall_training_score, employee_id)
        )

        cur.execute(
            """
            SELECT DISTINCT cycle_id
            FROM performance_result
            WHERE employee_id = %s
            """,
            (employee_id,)
        )
        for (c_id,) in cur.fetchall():
            if c_id:
                try:
                    from routes.dashboard import update_final_performance_score
                    update_final_performance_score(cur, employee_id, c_id)
                except Exception:
                    pass

        conn.commit()

        return jsonify({
            "message": "Attendance marked successfully",
            "employee_id": employee_id,
            "session_id": session_id,
            "attendance_status": attendance_status,
            "attendance_score": program_attendance_score
        }), 200

    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()


# ---------------------------------------------------------
# GET ATTENDANCE FOR A TRAINING SESSION
# ---------------------------------------------------------
@training_bp.route(
    "/training/<int:program_id>/sessions/<int:session_id>/attendance",
    methods=["GET"]
)
def get_training_attendance(program_id, session_id):
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT
                e.employee_id,
                e.employee_code,
                e.first_name,
                e.last_name,
                d.department_name,
                COALESCE(
                    ta.attendance_status,
                    'Not Marked'
                ) AS attendance_status
            FROM training_records tr
            JOIN employees e
                ON tr.employee_id = e.employee_id
            LEFT JOIN departments d
                ON e.department_id = d.department_id
            LEFT JOIN training_attendance ta
                ON ta.employee_id = e.employee_id
                AND ta.session_id = %s
            WHERE tr.program_id = %s
            ORDER BY e.first_name, e.last_name
            """,
            (session_id, program_id)
        )

        rows = cur.fetchall()

        attendance = [
            {
                "employee_id": row[0],
                "employee_code": row[1] or "",
                "employee_name": f"{row[2] or ''} {row[3] or ''}".strip(),
                "department": row[4] or "",
                "attendance_status": row[5]
            }
            for row in rows
        ]

        return jsonify(attendance), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()


# ---------------------------------------------------------
# GET ATTENDANCE SCORE FOR AN EMPLOYEE IN A PROGRAM
# ---------------------------------------------------------
@training_bp.route(
    "/training/<int:program_id>/employees/<int:employee_id>/attendance-score",
    methods=["GET"]
)
def get_training_attendance_score(program_id, employee_id):
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT
                COUNT(*) FILTER (
                    WHERE ta.attendance_status = 'Attended'
                ) AS attended_sessions,

                COUNT(*) FILTER (
                    WHERE ta.attendance_status = 'Absent'
                ) AS absent_sessions,

                COUNT(*) FILTER (
                    WHERE ta.attendance_status = 'Approved Leave'
                ) AS approved_leave_sessions

            FROM training_sessions ts
            JOIN training_records tr
                ON tr.program_id = ts.program_id
               AND tr.employee_id = %s

            LEFT JOIN training_attendance ta
                ON ta.session_id = ts.session_id
               AND ta.employee_id = %s

            WHERE ts.program_id = %s
            """,
            (
                employee_id,
                employee_id,
                program_id
            )
        )

        row = cur.fetchone()

        attended = row[0] or 0
        absent = row[1] or 0
        approved_leave = row[2] or 0

        # Approved Leave is excluded from denominator
        expected_sessions = attended + absent

        if expected_sessions > 0:
            attendance_score = round((attended / expected_sessions) * 100.0, 2)
        else:
            attendance_score = None

        return jsonify({
            "employee_id": employee_id,
            "program_id": program_id,
            "attended_sessions": attended,
            "absent_sessions": absent,
            "approved_leave_sessions": approved_leave,
            "expected_sessions": expected_sessions,
            "attendance_score": attendance_score
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()

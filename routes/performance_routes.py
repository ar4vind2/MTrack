from flask import Blueprint, jsonify, request
from config import get_db_connection

performance_bp = Blueprint(
    "performance",
    __name__,
    url_prefix="/api"
)


# ---------------------------------------------------------
# GET PERFORMANCE FOR ONE EMPLOYEE
# ---------------------------------------------------------
@performance_bp.route("/performance/<int:employee_id>", methods=["GET"])
def get_employee_performance(employee_id):
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cycle_id = request.args.get("cycle_id", type=int)
        if not cycle_id:
            cur.execute("SELECT cycle_id, start_date, end_date FROM appraisal_cycles WHERE status = 'Active' ORDER BY cycle_id DESC LIMIT 1")
            ac_row = cur.fetchone()
            cycle_id = ac_row[0] if ac_row else None
            cycle_start = ac_row[1] if ac_row else None
            cycle_end = ac_row[2] if ac_row else None
        else:
            cur.execute("SELECT start_date, end_date FROM appraisal_cycles WHERE cycle_id = %s", (cycle_id,))
            ac_row = cur.fetchone()
            cycle_start = ac_row[0] if ac_row else None
            cycle_end = ac_row[1] if ac_row else None

        cur.execute(
            """
            SELECT
                e.employee_id,

                -- KPI
                (
                    SELECT AVG(LEAST(100.0,
                        (kr.achieved_value::FLOAT / NULLIF(ek.assigned_target, 0)) * 100.0
                    ))
                    FROM employee_kpi ek
                    JOIN LATERAL (
                        SELECT kr.achieved_value
                        FROM kpi_records kr
                        WHERE kr.employee_id = ek.employee_id
                          AND kr.kpi_id = ek.kpi_id
                          AND kr.evaluation_month >= DATE_TRUNC('month', ek.start_date)
                          AND kr.evaluation_month <= DATE_TRUNC('month', ek.end_date)
                        ORDER BY kr.evaluation_month DESC, kr.created_at DESC
                        LIMIT 1
                    ) kr ON TRUE
                    WHERE ek.employee_id = e.employee_id
                      AND (%s::INTEGER IS NULL OR ek.cycle_id = %s)
                      AND ek.assigned_target IS NOT NULL
                      AND ek.assigned_target > 0
                ) AS kpi_score,

                -- Manager appraisal (scaled 1-5 to 0-100)
                (
                    SELECT m.total_score
                    FROM manager_appraisal m
                    WHERE m.employee_id = e.employee_id
                      AND (%s::INTEGER IS NULL OR m.cycle_id = %s)
                    ORDER BY m.appraisal_date DESC
                    LIMIT 1
                ) AS manager_score,

                -- Attendance (Cycle-level dynamic calculation)
                COALESCE(
                    (
                        SELECT
                            CASE
                                WHEN COUNT(*) FILTER (WHERE LOWER(TRIM(a.status)) NOT IN ('weekly off', 'holiday')) = 0 THEN 100.00
                                ELSE
                                    ROUND(
                                        (
                                            COUNT(*) FILTER (WHERE LOWER(TRIM(a.status)) = 'present')::DECIMAL
                                            + (COUNT(*) FILTER (WHERE LOWER(TRIM(a.status)) IN ('half day', 'half-day'))::DECIMAL * 0.5)
                                        )
                                        /
                                        COUNT(*) FILTER (WHERE LOWER(TRIM(a.status)) NOT IN ('weekly off', 'holiday'))::DECIMAL
                                        * 100,
                                        2
                                    )
                            END
                        FROM attendance a
                        WHERE a.employee_id = e.employee_id
                          AND (%s::DATE IS NULL OR a.attendance_date >= %s::DATE)
                          AND (%s::DATE IS NULL OR a.attendance_date <= %s::DATE)
                    ),
                    100.00
                ) AS attendance_score,

                -- Behaviour
                (
                    SELECT AVG(
                        (
                            b.integrity +
                            b.professionalism +
                            b.leadership +
                            b.accountability +
                            b.time_management +
                            b.adaptability +
                            b.learning_ability
                        ) / 7.0 * 20
                    )
                    FROM behaviour_rating b
                    WHERE b.employee_id = e.employee_id
                      AND (%s::INTEGER IS NULL OR b.cycle_id = %s)
                ) AS behaviour_score,

                -- Self appraisal
                (
                    SELECT s.self_score
                    FROM self_appraisal s
                    WHERE s.employee_id = e.employee_id
                      AND (%s::INTEGER IS NULL OR s.cycle_id = %s)
                    ORDER BY s.created_at DESC
                    LIMIT 1
                ) AS self_score,

                -- Training Attendance Score
                (
                    SELECT
                        CASE
                            WHEN COUNT(*) FILTER (
                                WHERE ta.attendance_status IN ('Attended', 'Absent')
                            ) = 0
                                THEN NULL
                            ELSE
                                COUNT(*) FILTER (
                                    WHERE ta.attendance_status = 'Attended'
                                )::DECIMAL
                                /
                                COUNT(*) FILTER (
                                    WHERE ta.attendance_status IN ('Attended', 'Absent')
                                )
                                * 100
                        END
                    FROM training_records tr
                    LEFT JOIN training_sessions ts
                        ON ts.program_id = tr.program_id
                    LEFT JOIN training_attendance ta
                        ON ta.session_id = ts.session_id
                        AND ta.employee_id = tr.employee_id
                    WHERE tr.employee_id = e.employee_id
                ) AS training_score

            FROM employees e
            WHERE e.employee_id = %s
            """,
            (
                cycle_id, cycle_id,
                cycle_id, cycle_id,
                cycle_start, cycle_start, cycle_end, cycle_end,
                cycle_id, cycle_id,
                cycle_id, cycle_id,
                employee_id
            )
        )

        row = cur.fetchone()

        if not row:
            return jsonify({"error": "Employee not found"}), 404

        (
            emp_id,
            kpi_score,
            manager_score,
            attendance_score,
            behaviour_score,
            self_score,
            training_score
        ) = row

        kpi = float(kpi_score) if kpi_score is not None else None
        manager = float(manager_score) if manager_score is not None else None
        attendance = float(attendance_score) if attendance_score is not None else None
        behaviour = float(behaviour_score) if behaviour_score is not None else None
        self_score_val = float(self_score) if self_score is not None else None
        training = float(training_score) if training_score is not None else None

        missing = []
        if kpi is None:
            missing.append("KPI")
        if manager is None:
            missing.append("Manager appraisal")
        if attendance is None:
            missing.append("Attendance")
        if behaviour is None:
            missing.append("Behaviour assessment")
        if self_score_val is None:
            missing.append("Self appraisal")

        scores_dict = {
            "kpi": round(kpi, 2) if kpi is not None else None,
            "manager": round(manager, 2) if manager is not None else None,
            "attendance": round(attendance, 2) if attendance is not None else None,
            "behaviour": round(behaviour, 2) if behaviour is not None else None,
            "self_appraisal": round(self_score_val, 2) if self_score_val is not None else None,
            "training": round(training, 2) if training is not None else None
        }

        weights_dict = {
            "kpi": 40,
            "manager": 30,
            "attendance": 10,
            "behaviour": 10,
            "self_appraisal": 5,
            "training": 5
        }

        if missing:
            return jsonify({
                "employee_id": emp_id,
                "status": "Incomplete",
                "missing_assessments": missing,
                "missing_components": missing,
                "final_score": None,
                "rating": "Incomplete",
                "recommendations": [
                    "Pending assessments: " + ", ".join(missing)
                ],
                "scores": scores_dict,
                "weights": weights_dict
            }), 200

        weights = {
            "kpi": 0.40,
            "manager": 0.30,
            "attendance": 0.10,
            "behaviour": 0.10,
            "self_appraisal": 0.05
        }

        component_scores = {
            "kpi": kpi,
            "manager": manager,
            "attendance": attendance,
            "behaviour": behaviour,
            "self_appraisal": self_score_val
        }

        if training is not None:
            weights["training"] = 0.05
            component_scores["training"] = training

        applicable_weight = sum(weights.values())
        final_score = sum(component_scores[key] * weights[key] for key in component_scores) / applicable_weight

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

        recommendations = [recommendation]

        return jsonify({
            "employee_id": emp_id,
            "status": "Completed",
            "scores": scores_dict,
            "weights": weights_dict,
            "final_score": round(final_score, 2),
            "rating": rating,
            "recommendations": recommendations
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()


# ---------------------------------------------------------
# GET ALL EMPLOYEE PERFORMANCE RESULTS
# ---------------------------------------------------------
@performance_bp.route("/performance-results", methods=["GET"])
def get_performance_results():
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        target_cycle_id = request.args.get("cycle_id", type=int)
        if not target_cycle_id:
            cur.execute("SELECT cycle_id, start_date, end_date FROM appraisal_cycles WHERE status = 'Active' ORDER BY cycle_id DESC LIMIT 1")
            ac_row = cur.fetchone()
            target_cycle_id = ac_row[0] if ac_row else 1
            cycle_start = ac_row[1] if ac_row else None
            cycle_end = ac_row[2] if ac_row else None
        else:
            cur.execute("SELECT start_date, end_date FROM appraisal_cycles WHERE cycle_id = %s", (target_cycle_id,))
            ac_row = cur.fetchone()
            cycle_start = ac_row[0] if ac_row else None
            cycle_end = ac_row[1] if ac_row else None

        cur.execute(
            """
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
            ORDER BY e.first_name, e.last_name
            """
        )

        employees = cur.fetchall()

        results = []

        for employee in employees:
            employee_id = employee[0]
            employee_code = employee[1] or ""
            first_name = employee[2] or ""
            last_name = employee[3] or ""
            department = employee[4] or "—"
            designation = employee[5] or "—"

            cur.execute(
                """
                SELECT
                    -- KPI
                    (
                        SELECT AVG(LEAST(100.0, (kr.achieved_value::FLOAT / NULLIF(ek.assigned_target, 0)) * 100.0))
                        FROM employee_kpi ek
                        JOIN LATERAL (
                            SELECT kr.achieved_value
                            FROM kpi_records kr
                            WHERE kr.employee_id = ek.employee_id
                              AND kr.kpi_id = ek.kpi_id
                              AND kr.evaluation_month >= DATE_TRUNC('month', ek.start_date)
                              AND kr.evaluation_month <= DATE_TRUNC('month', ek.end_date)
                            ORDER BY kr.evaluation_month DESC, kr.created_at DESC
                            LIMIT 1
                        ) kr ON TRUE
                        WHERE ek.employee_id = %s
                          AND (%s::INTEGER IS NULL OR ek.cycle_id = %s)
                          AND ek.assigned_target IS NOT NULL
                          AND ek.assigned_target > 0
                    ),

                    -- Manager (scaled 1-5 to 0-100)
                    (
                        SELECT m.total_score
                        FROM manager_appraisal m
                        WHERE m.employee_id = %s
                          AND (%s::INTEGER IS NULL OR m.cycle_id = %s)
                        ORDER BY m.appraisal_date DESC
                        LIMIT 1
                    ),

                    -- Attendance (Cycle-level dynamic calculation)
                    COALESCE(
                        (
                            SELECT
                                CASE
                                    WHEN COUNT(*) FILTER (WHERE LOWER(TRIM(a.status)) NOT IN ('weekly off', 'holiday')) = 0 THEN 100.00
                                    ELSE
                                        ROUND(
                                            (
                                                COUNT(*) FILTER (WHERE LOWER(TRIM(a.status)) = 'present')::DECIMAL
                                                + (COUNT(*) FILTER (WHERE LOWER(TRIM(a.status)) IN ('half day', 'half-day'))::DECIMAL * 0.5)
                                            )
                                            /
                                            COUNT(*) FILTER (WHERE LOWER(TRIM(a.status)) NOT IN ('weekly off', 'holiday'))::DECIMAL
                                            * 100,
                                            2
                                        )
                                END
                            FROM attendance a
                            WHERE a.employee_id = %s
                              AND (%s::DATE IS NULL OR a.attendance_date >= %s::DATE)
                              AND (%s::DATE IS NULL OR a.attendance_date <= %s::DATE)
                        ),
                        100.00
                    ),

                    -- Behaviour
                    (
                        SELECT AVG(
                            (
                                b.integrity +
                                b.professionalism +
                                b.leadership +
                                b.accountability +
                                b.time_management +
                                b.adaptability +
                                b.learning_ability
                            ) / 7.0 * 20
                        )
                        FROM behaviour_rating b
                        WHERE b.employee_id = %s
                          AND (%s::INTEGER IS NULL OR b.cycle_id = %s)
                    ),

                    -- Self appraisal
                    (
                        SELECT s.self_score
                        FROM self_appraisal s
                        WHERE s.employee_id = %s
                          AND (%s::INTEGER IS NULL OR s.cycle_id = %s)
                        ORDER BY s.created_at DESC
                        LIMIT 1
                    ),

                    -- Training Attendance Score
                    (
                        SELECT
                            CASE
                                WHEN COUNT(*) FILTER (
                                    WHERE ta.attendance_status IN ('Attended', 'Absent')
                                ) = 0
                                    THEN NULL
                                ELSE
                                    COUNT(*) FILTER (
                                        WHERE ta.attendance_status = 'Attended'
                                    )::DECIMAL
                                    /
                                    COUNT(*) FILTER (
                                        WHERE ta.attendance_status IN ('Attended', 'Absent')
                                    )
                                    * 100
                            END
                        FROM training_records tr
                        LEFT JOIN training_sessions ts
                            ON ts.program_id = tr.program_id
                        LEFT JOIN training_attendance ta
                            ON ta.session_id = ts.session_id
                            AND ta.employee_id = tr.employee_id
                        WHERE tr.employee_id = %s
                    ) AS training_score
                """,
                (
                    employee_id, target_cycle_id, target_cycle_id,
                    employee_id, target_cycle_id, target_cycle_id,
                    employee_id, cycle_start, cycle_start, cycle_end, cycle_end,
                    employee_id, target_cycle_id, target_cycle_id,
                    employee_id, target_cycle_id, target_cycle_id,
                    employee_id
                )
            )

            scores_row = cur.fetchone()

            # Read assessment scores without treating missing assessments as zero
            kpi = float(scores_row[0]) if scores_row and scores_row[0] is not None else None
            manager = float(scores_row[1]) if scores_row and scores_row[1] is not None else None
            attendance = float(scores_row[2]) if scores_row and scores_row[2] is not None else None
            behaviour = float(scores_row[3]) if scores_row and scores_row[3] is not None else None
            self_score = float(scores_row[4]) if scores_row and scores_row[4] is not None else None
            training = float(scores_row[5]) if scores_row and scores_row[5] is not None else None

            # Required assessments
            required = {
                "KPI": kpi,
                "Manager appraisal": manager,
                "Attendance": attendance,
                "Behaviour assessment": behaviour,
                "Self appraisal": self_score
            }

            missing = [name for name, value in required.items() if value is None]

            # Optional training is not included in the missing list
            if missing:
                rating = "Incomplete"
                recommendations = ["Pending assessments: " + ", ".join(missing)]
                final_score = None
            else:
                kpi = float(kpi)
                manager = float(manager)
                attendance = float(attendance)
                behaviour = float(behaviour)
                self_score = float(self_score)
                training = float(training) if training is not None else None

                weights = {
                    "kpi": 0.40,
                    "manager": 0.30,
                    "attendance": 0.10,
                    "behaviour": 0.10,
                    "self": 0.05
                }

                component_scores = {
                    "kpi": kpi,
                    "manager": manager,
                    "attendance": attendance,
                    "behaviour": behaviour,
                    "self": self_score
                }

                if training is not None:
                    weights["training"] = 0.05
                    component_scores["training"] = training

                total_weight = sum(weights.values())
                final_score = sum(
                    component_scores[key] * weights[key]
                    for key in component_scores
                ) / total_weight

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

                recommendations = [recommendation]

            # Get manager's remarks
            cur.execute(
                """
                SELECT manager_comments
                FROM manager_appraisal
                WHERE employee_id = %s
                  AND (%s::INTEGER IS NULL OR cycle_id = %s)
                ORDER BY appraisal_date DESC
                LIMIT 1
                """,
                (employee_id, target_cycle_id, target_cycle_id)
            )
            manager_comments_row = cur.fetchone()
            manager_comments = manager_comments_row[0] if manager_comments_row and manager_comments_row[0] else "No remarks available"

            # Upsert into performance_result
            cur.execute(
                """
                INSERT INTO performance_result
                (
                    employee_id,
                    cycle_id,
                    kpi_score,
                    attendance_score,
                    manager_score,
                    behaviour_score,
                    self_appraisal_score,
                    training_score,
                    final_score,
                    rating,
                    recommendation
                )
                VALUES (
                    %s,
                    %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (employee_id, cycle_id)
                DO UPDATE SET
                    kpi_score = EXCLUDED.kpi_score,
                    attendance_score = EXCLUDED.attendance_score,
                    manager_score = EXCLUDED.manager_score,
                    behaviour_score = EXCLUDED.behaviour_score,
                    self_appraisal_score = EXCLUDED.self_appraisal_score,
                    training_score = EXCLUDED.training_score,
                    final_score = EXCLUDED.final_score,
                    rating = EXCLUDED.rating,
                    recommendation = EXCLUDED.recommendation
                """,
                (
                    employee_id,
                    target_cycle_id,
                    kpi,
                    attendance,
                    manager,
                    behaviour,
                    self_score,
                    training,
                    final_score,
                    rating,
                    ", ".join(recommendations)
                )
            )

            results.append({
                "employee_id": employee_id,
                "employee_code": employee_code,
                "name": f"{first_name} {last_name}".strip(),
                "department": department,
                "designation": designation,
                "cycle_id": target_cycle_id,
                "kpi_score": round(kpi, 2) if kpi is not None else None,
                "manager_score": round(manager, 2) if manager is not None else None,
                "attendance_score": round(attendance, 2) if attendance is not None else None,
                "behaviour_score": round(behaviour, 2) if behaviour is not None else None,
                "self_appraisal_score": round(self_score, 2) if self_score is not None else None,
                "training_score": round(training, 2) if training is not None else None,
                "score": round(final_score, 2) if final_score is not None else None,
                "rating": rating,
                "manager_comments": manager_comments,
                "recommendations": recommendations,
                "status": "Incomplete" if missing else "Completed",
                "missing_components": missing
            })

        conn.commit()
        return jsonify(results), 200

    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()


# ---------------------------------------------------------
# GET PERFORMANCE HISTORY FOR ONE EMPLOYEE
# ---------------------------------------------------------
@performance_bp.route("/performance-history/<int:employee_id>", methods=["GET"])
def get_performance_history(employee_id):
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT
                pr.cycle_id,
                ac.cycle_name,
                pr.final_score,
                pr.rating,
                pr.recommendation,
                pr.self_appraisal_score,
                pr.manager_score,
                COALESCE(NULLIF(TRIM(CONCAT(m.first_name, ' ', m.last_name)), ''), 'Manager') AS reviewer_name
            FROM performance_result pr
            LEFT JOIN appraisal_cycles ac ON pr.cycle_id = ac.cycle_id
            LEFT JOIN employees e ON pr.employee_id = e.employee_id
            LEFT JOIN employees m ON e.manager_id = m.employee_id
            WHERE pr.employee_id = %s
            ORDER BY pr.cycle_id DESC
            """,
            (employee_id,)
        )

        rows = cur.fetchall()

        history = [
            {
                "cycle_id": row[0],
                "cycle_name": row[1] or f"Cycle {row[0]}",
                "appraisal_year": row[1] or f"Cycle {row[0]}",
                "final_score": float(row[2]) if row[2] is not None else None,
                "rating": row[3] or "N/A",
                "recommendation": row[4] or "N/A",
                "self_score": float(row[5]) if row[5] is not None else None,
                "manager_score": float(row[6]) if row[6] is not None else None,
                "reviewer_name": row[7] or "Manager",
                "status": "Incomplete" if row[2] is None else "Completed"
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
# GET ALL APPRAISAL CYCLES (FOR DROPDOWNS & HISTORY)
# ---------------------------------------------------------
@performance_bp.route("/appraisal-cycles", methods=["GET"])
def get_appraisal_cycles_list():
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT
                cycle_id,
                cycle_name,
                start_date,
                end_date,
                status
            FROM appraisal_cycles
            ORDER BY cycle_id DESC
            """
        )
        rows = cur.fetchall()

        cycles = [
            {
                "cycle_id": row[0],
                "cycle_name": row[1] or f"Cycle {row[0]}",
                "start_date": row[2].isoformat() if row[2] else None,
                "end_date": row[3].isoformat() if row[3] else None,
                "status": row[4] or "Active"
            }
            for row in rows
        ]

        return jsonify(cycles), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()


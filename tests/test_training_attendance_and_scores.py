import pytest
from unittest.mock import MagicMock
from routes.dashboard import calculate_training_score, update_final_performance_score


def test_calculate_training_score_returns_none_when_no_records():
    cursor = MagicMock()
    cursor.fetchone.return_value = (0, 0)  # attended=0, evaluated=0
    assert calculate_training_score(cursor, employee_id=999) is None

    cursor.fetchone.return_value = None
    assert calculate_training_score(cursor, employee_id=999) is None


def test_calculate_training_score_excludes_approved_leave():
    cursor = MagicMock()
    # 3 attended, 3 evaluated (1 approved leave excluded from evaluated)
    cursor.fetchone.return_value = (3, 3)
    score = calculate_training_score(cursor, employee_id=1)
    assert score == 100.0


def test_calculate_training_score_partial_attendance():
    cursor = MagicMock()
    # 2 attended, 3 evaluated (2 attended, 1 absent, 1 approved leave excluded)
    cursor.fetchone.return_value = (2, 3)
    score = calculate_training_score(cursor, employee_id=1)
    assert score == 66.67


def test_calculate_training_score_genuine_zero():
    cursor = MagicMock()
    # 0 attended, 2 evaluated (all absent)
    cursor.fetchone.return_value = (0, 2)
    score = calculate_training_score(cursor, employee_id=1)
    assert score == 0.0


def test_final_performance_score_normalization_without_training():
    cursor = MagicMock()
    # kpi, manager, attendance, behaviour, self, training=None
    cursor.fetchone.return_value = (80.0, 80.0, 80.0, 80.0, 80.0, None)
    
    score = update_final_performance_score(cursor, employee_id=1, cycle_id=1)
    # Should normalize over 0.95 -> (80*0.95)/0.95 = 80.0
    assert score == 80.0


def test_final_performance_score_normalization_with_training():
    cursor = MagicMock()
    # kpi, manager, attendance, behaviour, self, training=100.0
    cursor.fetchone.return_value = (80.0, 80.0, 80.0, 80.0, 80.0, 100.0)
    
    score = update_final_performance_score(cursor, employee_id=1, cycle_id=1)
    # 80*0.95 + 100*0.05 = 76 + 5 = 81.0
    assert score == 81.0


def test_training_details_template_ui():
    with open("templates/training_details.html", "r", encoding="utf-8") as f:
        html = f.read()

    # HR issue certificate action exists
    assert "Issue Certificate" in html
    assert "Pending Employee Upload" not in html
    # Real-time score element ID exists
    assert "att-score-${emp.employee_id}" in html
    # Dropdown refresh without re-showing modal exists
    assert "refreshSessionsDropdown" in html
    # Global modal backdrop cleanup exists
    assert "hidden.bs.modal" in html


def test_employee_training_template_ui():
    with open("templates/employee_training.html", "r", encoding="utf-8") as f:
        html = f.read()

    # Pending HR Issuance displayed
    assert "Certificate Pending HR Issuance" in html
    # Employee upload modal removed
    assert "uploadCertModal" not in html
    # Details & Sessions button exists
    assert "Details & Sessions" in html
    # Training details modal exists
    assert "trainingDetailsModal" in html
    assert "modalSessionsTableBody" in html
    assert "modalTrainingCode" in html
    assert "modalAttendanceRate" in html


def test_performance_details_recommendation_overflow_fix_ui():
    with open("templates/employee_performance_details.html", "r", encoding="utf-8") as f:
        html = f.read()

    # Committee Recommendation element exists
    assert "committeeActionRecommendation" in html
    # Wrapping style and text-wrap classes exist
    assert "text-wrap" in html
    assert "text-break" in html
    assert "white-space: normal" in html
    assert "word-break: break-word" in html


def test_get_employee_program_sessions_api():
    from unittest.mock import patch
    from datetime import date, time
    from flask import Flask
    from routes.training_routes import training_bp

    app = Flask(__name__)
    app.register_blueprint(training_bp)

    with patch("routes.training_routes.get_db_connection") as mock_conn:
        cursor = MagicMock()
        mock_conn.return_value.cursor.return_value = cursor
        cursor.fetchall.return_value = [
            (1, date(2026, 10, 20), "Muthoot Core Culture", time(10, 0), time(12, 0), "Attended")
        ]

        with app.test_client() as client:
            res = client.get("/api/training/10/employees/5/sessions")
            assert res.status_code == 200
            data = res.get_json()
            assert len(data) == 1
            assert data[0]["session_name"] == "Muthoot Core Culture"
            assert data[0]["attendance_status"] == "Attended"
            assert data[0]["start_time"] == "10:00"
            assert data[0]["end_time"] == "12:00"
